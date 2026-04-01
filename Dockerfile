# Utiliser une image Python officielle légère
FROM python:3.11-slim

# Empêcher Python de générer des fichiers .pyc et forcer l'affichage des logs en temps réel
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Définir le répertoire de travail
WORKDIR /app

# Installer les dépendances système nécessaires pour MariaDB/MySQL et Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmariadb-dev \
    libjpeg-dev \
    zlib1g-dev \
    pkg-config \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

# Copier le reste du projet
COPY . .

# Exposer le port par défaut (harmonisé avec docker-compose)
EXPOSE 5500

# Commande par défaut
CMD ["gunicorn", "passion_retro.wsgi:application", "--bind", "0.0.0.0:5500"]
