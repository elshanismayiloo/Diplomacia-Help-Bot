# -*- coding: utf-8 -*-
"""
Telegraph inteqrasiyası - "Necə etməli?" təlimat məqaləsini avtomatik yaradır.

Bot ilk dəfə işə düşəndə (əgər TELEGRAPH_HELP_URL mühit dəyişəni verilməyibsə)
bu modul:
  1. Telegraph-da anonim hesab yaradır,
  2. docs/images/ qovluğundakı addım şəkillərini yükləyir,
  3. Mətn + şəkillərdən ibarət məqalə səhifəsi qurur,
  4. Səhifənin URL-ni qaytarır.

Yaranan URL-i Railway-də TELEGRAPH_HELP_URL dəyişəni kimi əlavə etsən,
bot hər yenidən başlayanda təzə səhifə yaratmaz, mövcud olanı istifadə edər.
"""

import os
import json
import logging
import requests

logger = logging.getLogger(__name__)

TELEGRAPH_API = "https://api.telegra.ph"
TELEGRAPH_UPLOAD = "https://telegra.ph/upload"

IMAGES_DIR = os.path.dirname(__file__)

PAGE_TITLE = "Diplomacia Gəlir Hesablayıcısı — Məlumatları Necə Toplamalı?"
AUTHOR_NAME = "Diplomacia Gəlir Hesablayıcısı"

STEPS = [
    {
        "title": "1. Fabriklər siyahısına keç",
        "text": "Baş səhifədən FABRİKLƏR bölməsinə keç.",
        "image": "step1.jpg",
    },
    {
        "title": "2. Ən yüksək fabrikləri araşdır",
        "text": "Hər bir resurs növü üzrə (Dəri, Qızıl, Neft, NTE) ən yüksək səviyyəli fabrikləri yoxla.",
        "image": "step2.jpg",
    },
    {
        "title": "3. İstehsal miqdarını yaz",
        "text": "Hər 1 dəfə işlədikdə qazana biləcəyin miqdarı kənara yaz (şəkildəki nümunədə 2 428 ədəd).",
        "image": "step3.jpg",
    },
    {
        "title": "4. Bazara keç",
        "text": "İş səhifəsindən və ya Baş səhifənin yan menyusundan Bazara keçid et.",
        "image": "step4.jpg",
    },
    {
        "title": "5. Cari qiymətləri yaz",
        "text": "Hər bir resurs növü üzrə cari qiyməti kənara yaz. Qiymətlərin artma-azalma "
                 "tendensiyasını izləmək də tövsiyə olunur - bu, 'durğun/hərəkətli bazar' "
                 "suallarına cavab verməyinə kömək edəcək.",
        "image": "step5.jpg",
    },
]

INTRO = (
    "Bu qısa təlimat, Diplomacia Gəlir Hesablayıcı botuna lazım olan rəqəmləri "
    "oyunun içində necə tapacağını addım-addım göstərir. Bu 5 addımı tamamladıqdan "
    "sonra Telegram-da bota /start yazıb topladığın rəqəmləri daxil edə bilərsən."
)

OUTRO = (
    "Hazırsan! İndi Telegram-da bota qayıdıb /start yaz və yuxarıda topladığın "
    "rəqəmləri suallara uyğun daxil et."
)


def _create_account():
    resp = requests.post(f"{TELEGRAPH_API}/createAccount", data={
        "short_name": "DiplomaciaBot",
        "author_name": AUTHOR_NAME,
    }, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegraph createAccount xətası: {data}")
    return data["result"]["access_token"]


def _upload_image(filename: str) -> str:
    path = os.path.join(IMAGES_DIR, filename)
    with open(path, "rb") as f:
        resp = requests.post(TELEGRAPH_UPLOAD, files={"file": (filename, f, "image/jpeg")}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list) and data and "src" in data[0]:
        return "https://telegra.ph" + data[0]["src"]
    raise RuntimeError(f"Telegraph şəkil yükləmə xətası: {data}")


def _build_content(image_urls: dict):
    content = [{"tag": "p", "children": [INTRO]}]
    for step in STEPS:
        content.append({"tag": "h4", "children": [step["title"]]})
        content.append({"tag": "p", "children": [step["text"]]})
        img_url = image_urls.get(step["image"])
        if img_url:
            content.append({"tag": "figure", "children": [
                {"tag": "img", "attrs": {"src": img_url}},
            ]})
    content.append({"tag": "p", "children": [OUTRO]})
    return content


def _create_page(access_token: str, content: list) -> str:
    resp = requests.post(f"{TELEGRAPH_API}/createPage", data={
        "access_token": access_token,
        "title": PAGE_TITLE,
        "author_name": AUTHOR_NAME,
        "content": json.dumps(content, ensure_ascii=False),
        "return_content": "false",
    }, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegraph createPage xətası: {data}")
    return data["result"]["url"]


def create_help_article() -> str:
    """Telegraph-da təlimat məqaləsini yaradır və URL-ni qaytarır.
    Şəbəkə və ya Telegraph xətası olarsa exception qaldırır - çağıran tərəf
    bunu tutub fallback davranışına keçməlidir."""
    access_token = _create_account()
    image_urls = {}
    for step in STEPS:
        try:
            image_urls[step["image"]] = _upload_image(step["image"])
        except Exception as e:
            logger.warning("Şəkil yüklənmədi (%s): %s", step["image"], e)
    content = _build_content(image_urls)
    return _create_page(access_token, content)


def get_or_create_help_url() -> str:
    """Əvvəlcə TELEGRAPH_HELP_URL mühit dəyişənini yoxlayır; yoxdursa yeni
    məqalə yaradır. Xəta baş verərsə None qaytarır (bot yenə də işləməyə davam edir)."""
    existing = os.environ.get("TELEGRAPH_HELP_URL")
    if existing:
        return existing
    try:
        url = create_help_article()
        logger.info("=" * 60)
        logger.info("Telegraph təlimat səhifəsi yaradıldı: %s", url)
        logger.info("Bunu Railway-də TELEGRAPH_HELP_URL dəyişəni kimi əlavə et ki,")
        logger.info("hər yenidən başlamada təzə səhifə yaranmasın.")
        logger.info("=" * 60)
        return url
    except Exception as e:
        logger.error("Telegraph məqaləsi yaradıla bilmədi: %s", e)
        return None
