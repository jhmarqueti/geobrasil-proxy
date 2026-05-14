"""
GeoBrasil Proxy — FastAPI
Faz proxy das requisições para os ImageServers e FeatureServers da CPRM/SGB,
resolvendo o bloqueio de CORS que impede chamadas diretas do browser.
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GeoBrasil Proxy",
    description="Proxy CORS para ImageServers e FeatureServers da CPRM/SGB",
    version="1.0.0"
)

# Libera CORS para qualquer origem (necessário para o app web chamar o proxy)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Domínios permitidos — só faz proxy para servidores da CPRM/SGB
ALLOWED_HOSTS = [
    "geoportal.cprm.gov.br",
    "geoportal.sgb.gov.br",
    "arcgisserver.cprm.gov.br",
    "geosgb.sgb.gov.br",
]

# Mapa de atalhos para os ImageServers geofísicos
IMAGE_SERVERS = {
IMAGE_SERVERS = {
    "ternario":  "https://geoportal.sgb.gov.br/image/rest/services/geofisica_ternario/ImageServer",
    "1dv":       "https://geoportal.sgb.gov.br/image/rest/services/geofisica_1dv/ImageServer",
    "mag":       "https://geoportal.sgb.gov.br/image/rest/services/geofisica_mag/ImageServer",
    "kperc":     "https://geoportal.sgb.gov.br/image/rest/services/geofisica_kperc/ImageServer",
    "uth":       "https://geoportal.sgb.gov.br/image/rest/services/geofisica_uth/ImageServer",
    "relevo":    "https://geoportal.sgb.gov.br/image/rest/services/relevo_30m/ImageServer",
}

FEATURE_SERVERS = {
    "aerogeofisica": "https://geoportal.sgb.gov.br/server/rest/services/geofisica/aerogeofisica/FeatureServer/0",
    "gravimetria":   "https://geoportal.sgb.gov.br/server/rest/services/geofisica/gravimetria/FeatureServer/0",
}
TIMEOUT = httpx.Timeout(30.0, connect=10.0)

SSL_VERIFY = False


def is_allowed(url: str) -> bool:
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    return any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


@app.get("/", summary="Health check")
def root():
    return {
        "status": "ok",
        "service": "GeoBrasil Proxy",
        "endpoints": {
            "image":   "/image/{layer_id}?bbox=...&width=...&height=...",
            "feature": "/feature/{layer_id}?where=...&outFields=...&f=geojson",
            "proxy":   "/proxy?url=<url_completa>",
            "layers":  "/layers",
        }
    }


@app.get("/layers", summary="Lista camadas disponíveis")
def list_layers():
    return {
        "image_servers": {k: v + "/exportImage" for k, v in IMAGE_SERVERS.items()},
        "feature_servers": {k: v + "/query" for k, v in FEATURE_SERVERS.items()},
    }


@app.get("/image/{layer_id}", summary="Exporta imagem georreferenciada de uma camada geofísica")
async def export_image(
    layer_id: str,
    bbox: str = Query(...,  description="minLon,minLat,maxLon,maxLat em WGS84"),
    width: int  = Query(800, ge=64, le=2048),
    height: int = Query(600, ge=64, le=2048),
    transparent: bool = Query(True),
    format: str = Query("png"),
):
    if layer_id not in IMAGE_SERVERS:
        raise HTTPException(404, f"Camada '{layer_id}' não encontrada. Disponíveis: {list(IMAGE_SERVERS.keys())}")

    base = IMAGE_SERVERS[layer_id]
    params = {
        "bbox":        bbox,
        "bboxSR":      "4326",
        "size":        f"{width},{height}",
        "imageSR":     "4326",
        "format":      format,
        "transparent": "true" if transparent else "false",
        "f":           "image",
    }

    url = f"{base}/exportImage"
    logger.info(f"Proxy image → {url} bbox={bbox} size={width}x{height}")

    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True, verify=False) as client:
        try:
            r = await client.get(url, params=params)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(e.response.status_code, f"Erro no servidor CPRM: {e}")
        except httpx.RequestError as e:
            raise HTTPException(502, f"Não foi possível conectar ao servidor CPRM: {e}")

    content_type = r.headers.get("content-type", "image/png")
    return Response(content=r.content, media_type=content_type)


@app.get("/feature/{layer_id}", summary="Consulta FeatureServer (polígonos, pontos)")
async def query_feature(
    layer_id: str,
    where: str          = Query("1=1"),
    outFields: str      = Query("*"),
    resultRecordCount: int = Query(200, le=1000),
    f: str              = Query("geojson"),
    geometry: str       = Query(None, description="Bbox para filtro espacial: xmin,ymin,xmax,ymax"),
):
    if layer_id not in FEATURE_SERVERS:
        raise HTTPException(404, f"Layer '{layer_id}' não encontrada. Disponíveis: {list(FEATURE_SERVERS.keys())}")

    base = FEATURE_SERVERS[layer_id]
    params = {
        "where":             where,
        "outFields":         outFields,
        "resultRecordCount": resultRecordCount,
        "f":                 f,
    }
    if geometry:
        params["geometry"] = geometry
        params["geometryType"] = "esriGeometryEnvelope"
        params["inSR"] = "4326"

    url = f"{base}/query"
    logger.info(f"Proxy feature → {url} where={where}")

    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True, verify=False) as client:
        try:
            r = await client.get(url, params=params)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(e.response.status_code, f"Erro CPRM: {e}")
        except httpx.RequestError as e:
            raise HTTPException(502, f"Conexão falhou: {e}")

    ct = r.headers.get("content-type", "application/json")
    return Response(content=r.content, media_type=ct)


@app.get("/proxy", summary="Proxy genérico para qualquer URL da CPRM/SGB")
async def generic_proxy(url: str = Query(..., description="URL completa do endpoint CPRM/SGB")):
    if not is_allowed(url):
        raise HTTPException(403, f"Host não permitido. Apenas domínios da CPRM/SGB são aceitos.")

    logger.info(f"Generic proxy → {url}")
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True, verify=False) as client:
        try:
            r = await client.get(url)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(e.response.status_code, str(e))
        except httpx.RequestError as e:
            raise HTTPException(502, str(e))

    ct = r.headers.get("content-type", "application/octet-stream")
    return Response(content=r.content, media_type=ct)
