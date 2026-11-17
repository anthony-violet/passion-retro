import os
import re
import uuid
from pathlib import Path
from urllib.parse import quote, urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import AddImgGallery

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif"}
FOLDER_NAME_RE = re.compile(r"^[\w\-. ]+$", re.UNICODE)


def _user_gallery_dir(user):
    return Path(settings.MEDIA_ROOT) / "galleries" / str(user.id)


def _clean_folder_name(name):
    name = (name or "").strip()
    if not name or name in (".", "..") or name.startswith("."):
        raise ValueError("Nom de dossier invalide.")
    if len(name) > 80:
        raise ValueError("Le nom du dossier ne doit pas dépasser 80 caractères.")
    if not FOLDER_NAME_RE.match(name):
        raise ValueError(
            "Le nom du dossier ne peut contenir que des lettres, des chiffres, "
            "des espaces, des points, des tirets et des underscores."
        )
    return name


def _clean_image_name(filename):
    filename = (filename or "").strip()
    if not filename or filename in (".", ".."):
        raise ValueError("Image invalide.")
    if filename != os.path.basename(filename) or "/" in filename or "\\" in filename:
        raise ValueError("Image invalide.")
    if Path(filename).suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError("Type de fichier non autorisé.")
    return filename


def _image_path(user_dir, folder_name, filename):
    folder_name = (folder_name or "").strip()
    if folder_name:
        folder_path = user_dir / _clean_folder_name(folder_name)
    else:
        folder_path = user_dir

    image_path = folder_path / _clean_image_name(filename)
    user_dir_resolved = user_dir.resolve()
    image_path_resolved = image_path.resolve()
    if user_dir_resolved != image_path_resolved.parent and user_dir_resolved not in image_path_resolved.parents:
        raise ValueError("Chemin d'image invalide.")
    return image_path


def _gallery_context(user, folder_name=""):
    user_dir = _user_gallery_dir(user)
    folders = []
    if user_dir.exists():
        folders = sorted(
            (
                path.name
                for path in user_dir.iterdir()
                if path.is_dir() and not path.name.startswith(".")
            ),
            key=str.lower,
        )

    current_folder = ""
    if (folder_name or "").strip():
        current_folder = _clean_folder_name(folder_name)
        image_dir = user_dir / current_folder
        if not image_dir.is_dir():
            raise ValueError("Dossier introuvable.")
    else:
        image_dir = user_dir

    images = []
    if image_dir.exists():
        for image_file in sorted(image_dir.iterdir(), key=lambda path: path.name.lower()):
            if not image_file.is_file() or image_file.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            relative_path = image_file.relative_to(Path(settings.MEDIA_ROOT)).as_posix()
            images.append(
                {
                    "name": image_file.name,
                    "url": f"{settings.MEDIA_URL.rstrip('/')}/{quote(relative_path)}",
                }
            )

    return {
        "images": images,
        "folders": folders,
        "current_folder": current_folder,
        "destinations": [folder for folder in folders if folder != current_folder],
    }


def _gallery_redirect(folder_name=""):
    url = reverse("home_gallery")
    if folder_name:
        url = f"{url}?{urlencode({'folder': folder_name})}"
    return redirect(url)


def _render_gallery(request, template_name):
    folder_name = (request.GET.get("folder") or "").strip()
    try:
        context = _gallery_context(request.user, folder_name)
    except ValueError as error:
        messages.error(request, str(error))
        return redirect("home_gallery")

    context["form"] = AddImgGallery()
    context["folder"] = context["current_folder"]
    context["page_title"] = f"Galerie de {request.user.username} - {settings.SITE_NAME}"
    context["page_description"] = f"Galerie personnelle de {request.user.username}."
    return render(request, template_name, context)


@login_required()
def home_gallery(request):
    return _render_gallery(request, "gallery/index.html")


@login_required()
def gallery_embed(request):
    return _render_gallery(request, "gallery/home.html")


@login_required()
def import_img(request):
    folder_name = (request.POST.get("folder") or request.GET.get("folder") or "").strip()
    is_popup = request.GET.get("popup") == "1"
    template_name = "gallery/import_popup.html" if is_popup else "gallery/form.html"

    if request.method == "POST":
        form = AddImgGallery(request.POST, request.FILES)
        if form.is_valid():
            try:
                if folder_name:
                    folder_name = _clean_folder_name(folder_name)
                    target_dir = _user_gallery_dir(request.user) / folder_name
                    if not target_dir.is_dir():
                        raise ValueError("Dossier introuvable.")
                images = form.cleaned_data["image"]
                for image in images:
                    save_image_to_gallery(image, request.user.id, folder_name)
            except ValueError as error:
                messages.error(request, str(error))
                if is_popup:
                    return render(
                        request,
                        template_name,
                        {"form": form, "folder": folder_name, "error": str(error)},
                    )
            else:
                if len(images) > 1:
                    messages.success(request, f"Vos {len(images)} images ont bien été ajoutées à la galerie.")
                else:
                    messages.success(request, "Votre image a bien été ajoutée à la galerie.")
                if is_popup:
                    return render(
                        request,
                        template_name,
                        {
                            "form": AddImgGallery(),
                            "folder": folder_name,
                            "success": True,
                            "imported_count": len(images),
                        },
                    )
                return _gallery_redirect(folder_name)
        elif is_popup:
            return render(
                request,
                template_name,
                {"form": form, "folder": folder_name, "error": "Veuillez corriger les erreurs ci-dessous."},
            )
    else:
        form = AddImgGallery()

    return render(request, template_name, {"form": form, "folder": folder_name})


@login_required()
@require_POST
def create_folder(request):
    folder_name = request.POST.get("name") or ""
    try:
        folder_name = _clean_folder_name(folder_name)
        user_dir = _user_gallery_dir(request.user)
        user_dir.mkdir(parents=True, exist_ok=True)

        folder_path = user_dir / folder_name
        if folder_path.exists():
            raise ValueError("Un dossier porte déjà ce nom.")

        folder_path.mkdir()
        (folder_path / "index.html").write_text("", encoding="utf-8")
        messages.success(request, f"Le dossier « {folder_name} » a été créé.")
        return _gallery_redirect(folder_name)
    except ValueError as error:
        messages.error(request, str(error))
        return _gallery_redirect()


@login_required()
@require_POST
def move_image(request):
    filename = request.POST.get("image") or ""
    source_folder = (request.POST.get("folder") or "").strip()
    target_folder = (request.POST.get("target") or "").strip()

    try:
        user_dir = _user_gallery_dir(request.user)
        source_path = _image_path(user_dir, source_folder, filename)

        if not source_path.is_file():
            raise ValueError("Image introuvable.")

        if target_folder:
            target_dir = user_dir / _clean_folder_name(target_folder)
            if not target_dir.is_dir():
                raise ValueError("Dossier de destination introuvable.")
        else:
            target_dir = user_dir

        target_path = target_dir / source_path.name
        if source_path == target_path:
            raise ValueError("L'image se trouve déjà dans ce dossier.")
        if target_path.exists():
            raise ValueError("Une image portant le même nom existe déjà dans ce dossier.")

        source_path.rename(target_path)
        messages.success(request, "L'image a été déplacée.")
    except (ValueError, FileNotFoundError) as error:
        messages.error(request, str(error))

    return _gallery_redirect(source_folder)


@login_required()
@require_POST
def delete_image(request):
    filename = request.POST.get("image") or ""
    folder_name = (request.POST.get("folder") or "").strip()

    try:
        image_path = _image_path(_user_gallery_dir(request.user), folder_name, filename)
        if not image_path.is_file():
            raise ValueError("Image introuvable.")
        image_path.unlink()
        messages.success(request, "L'image a été supprimée.")
    except (ValueError, FileNotFoundError) as error:
        messages.error(request, str(error))

    return _gallery_redirect(folder_name)


def save_image_to_gallery(image, user_id, folder_name=""):
    user_dir = Path(settings.MEDIA_ROOT) / "galleries" / str(user_id)
    target_dir = user_dir / folder_name if folder_name else user_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    # Créer un fichier index.html vide pour sécuriser le répertoire
    for directory in {user_dir, target_dir}:
        index_file_path = directory / "index.html"
        if not index_file_path.exists():
            index_file_path.write_text("", encoding="utf-8")

    extension = Path(image.name).suffix.lower()
    filename = f"{uuid.uuid4().hex}{extension}"
    while (target_dir / filename).exists():
        filename = f"{uuid.uuid4().hex}{extension}"

    file_path = target_dir / filename
    with open(file_path, "wb+") as destination:
        for chunk in image.chunks():
            destination.write(chunk)

    relative_path = file_path.relative_to(Path(settings.MEDIA_ROOT)).as_posix()
    return f"{settings.MEDIA_URL.rstrip('/')}/{quote(relative_path)}"
