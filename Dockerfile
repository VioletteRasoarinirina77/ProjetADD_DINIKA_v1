FROM python:3.12-slim

WORKDIR /app

COPY requirements-core.txt ./
RUN pip install --no-cache-dir --default-timeout=120 --retries 5 -r requirements-core.txt
# vectorbt (lourde : numba + llvmlite) n'est utilisée par aucun module : volontairement absente de l'image.
# Si le backtest multi-instruments vectorisé est codé un jour : pip install -r requirements-vectorbt.txt

COPY . .

# A3 : la disponibilité (exigence CDC non-fonctionnelle) doit être mesurable, pas seulement
# espérée. `docker ps` et `docker compose` marquent le conteneur "unhealthy" si /health ne répond
# plus, ce qui permet à Compose de le redémarrer (voir `restart: unless-stopped`) et à une
# supervision externe de le détecter. Pas de curl dans l'image slim : on interroge /health avec
# urllib (bibliothèque standard), sans dépendance supplémentaire.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/health', timeout=2)" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
