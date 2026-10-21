from pathlib import Path
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from ..extensions.pairing import LOCAL

router = APIRouter()
STATIC = Path(__file__).parent / 'static'


@router.get('/phone')
async def phone():
    return FileResponse(STATIC / 'phone.html')


@router.get('/phone.js')
async def phone_js():
    return FileResponse(STATIC / 'phone.js', media_type='text/javascript')


class PairBody(BaseModel):
    token: str = Field(min_length=20, max_length=500)


@router.post('/api/phone/pair')
async def pair(body: PairBody, request: Request):
    pairing = getattr(request.app.state, 'pairing', None)
    origin = request.headers.get('origin')
    if origin and urlsplit(origin).hostname != request.url.hostname:
        raise HTTPException(403, 'Idegen weboldal.')
    if pairing is None or not pairing.valid(body.token):
        raise HTTPException(401, 'Hibás vagy lejárt párosítási kód.')
    response = JSONResponse({'ok': True})
    response.set_cookie('jarvis_pair', body.token, httponly=True, samesite='strict', secure=request.url.scheme == 'https', max_age=86400)
    return response


@router.post('/api/phone/logout')
async def logout():
    response = JSONResponse({'ok': True})
    response.delete_cookie('jarvis_pair')
    return response
