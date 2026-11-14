from django.urls import path

from . import views

urlpatterns = [
    path("", views.home_gallery, name="home_gallery"),
    path("embed/", views.gallery_embed, name="gallery_embed"),
    path("import", views.import_img, name="import"),
    path("folder/create/", views.create_folder, name="gallery_create_folder"),
    path("image/move/", views.move_image, name="gallery_move_image"),
    path("image/delete/", views.delete_image, name="gallery_delete_image"),
]
