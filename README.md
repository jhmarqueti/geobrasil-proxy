# GeoBrasil Proxy

Proxy FastAPI que resolve o bloqueio de CORS para os ImageServers e FeatureServers da CPRM/SGB,
permitindo que o app GeoBrasil carregue imagens geofísicas georreferenciadas diretamente no browser.

## Endpoints

| Rota | Descrição |
|------|-----------|
| `GET /` | Health check |
| `GET /layers` | Lista todas as camadas disponíveis |
| `GET /image/{layer_id}` | Exporta imagem georreferenciada |
| `GET /feature/{layer_id}` | Consulta polígonos/pontos (GeoJSON) |
| `GET /proxy?url=...` | Proxy genérico para qualquer URL da CPRM |

### Camadas disponíveis (`/image/{layer_id}`)
- `ternario` — Composição ternária K-eTh-eU
- `1dv` — 1ª Derivada Vertical magnética
- `mag` — Campo Magnético Total
- `kperc` — Canal K (Potássio %)
- `uth` — Razão U/Th
- `relevo` — Relevo Sombreado 30m

### Exemplo de requisição
```
GET /image/ternario?bbox=-44.5,-21,-42.5,-19&width=800&height=600
GET /feature/aerogeofisica?where=1=1&f=geojson&resultRecordCount=100
```

---

## Deploy no Render (gratuito)

### 1. Instalar Git e fazer upload

Se não tiver Git instalado:
- Windows: https://git-scm.com/download/win
- Mac: `brew install git`

```bash
# Na pasta geobrasil-proxy:
git init
git add .
git commit -m "primeiro commit"
```

### 2. Criar repositório no GitHub

1. Acesse https://github.com e crie uma conta (se não tiver)
2. Clique em **New repository** → nome: `geobrasil-proxy`
3. Deixe **público** (necessário para o Render gratuito)
4. Copie a URL do repositório (ex: `https://github.com/seunome/geobrasil-proxy.git`)

```bash
git remote add origin https://github.com/seunome/geobrasil-proxy.git
git branch -M main
git push -u origin main
```

### 3. Deploy no Render

1. Acesse https://render.com e crie uma conta gratuita
2. Clique em **New +** → **Web Service**
3. Conecte sua conta GitHub
4. Selecione o repositório `geobrasil-proxy`
5. Render vai detectar o `render.yaml` automaticamente
6. Clique em **Create Web Service**
7. Aguarde ~3 minutos — o deploy é automático

Você receberá uma URL pública como:
```
https://geobrasil-proxy.onrender.com
```

### 4. Testar

Abra no browser:
```
https://geobrasil-proxy.onrender.com/
https://geobrasil-proxy.onrender.com/layers
https://geobrasil-proxy.onrender.com/image/ternario?bbox=-74,-34,-34,6&width=400&height=400
```

### 5. Atualizar o app GeoBrasil

No código do app, troque a constante `PROXY_BASE`:
```javascript
const PROXY_BASE = "https://geobrasil-proxy.onrender.com";
// Exemplo de chamada:
// ${PROXY_BASE}/image/ternario?bbox=-44.5,-21,-42.5,-19&width=800&height=600
```

---

## Rodar localmente (para testar antes do deploy)

```bash
# Instalar dependências
pip install -r requirements.txt

# Rodar o servidor
uvicorn main:app --reload --port 8000

# Acessar
# http://localhost:8000
# http://localhost:8000/docs  ← documentação interativa automática
```

---

## Notas importantes

- O plano gratuito do Render **dorme após 15 min** de inatividade. A primeira requisição pode demorar ~30s para "acordar" o servidor.
- Para produção sem delay, considere o plano Starter ($7/mês) ou migrate para Railway.
- O proxy só aceita URLs dos domínios `cprm.gov.br` e `sgb.gov.br` por segurança.
