"""
One-off verification script for dynamic Cloudinary gallery folders.
Run: python manage.py shell < scripts/verify_gallery_cloudinary_paths.py
"""
import os

from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import Instrument, User
from gallery.models import GalleryItem

TEST_IMAGE = os.path.join(
    "jamsession", "static", "images", "favicon", "favicon-96x96.png"
)


def get_or_create_test_user(username):
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": f"{username}@jamsession-lab.test",
            "instrument": Instrument.GUITAR,
        },
    )
    if created:
        user.set_password("test-only-password")
        user.save(update_fields=["password"])
    return user


def upload_for_user(username):
    user = get_or_create_test_user(username)
    item = GalleryItem(uploaded_by=user, title=f"Path test for {username}")

    with open(TEST_IMAGE, "rb") as image_file:
        uploaded = SimpleUploadedFile(
            f"{username}-gallery-test.png",
            image_file.read(),
            content_type="image/png",
        )

    item.file = uploaded
    field = GalleryItem._meta.get_field("file")
    field.pre_save(item, add=True)

    public_id = item.file.public_id
    folder = item.upload_options()["folder"]
    return {
        "username": username,
        "upload_options_folder": folder,
        "cloudinary_public_id": public_id,
        "cloudinary_url": item.file.url,
    }


print("=== upload_options() per utente (senza upload) ===")
for name in ("gallery_test_alice", "gallery_test_bob"):
    user = get_or_create_test_user(name)
    item = GalleryItem(uploaded_by=user)
    print(f"  {name}: {item.upload_options()}")

print("\n=== Upload reali su Cloudinary (pre_save, senza migrate) ===")
results = []
for name in ("gallery_test_alice", "gallery_test_bob"):
    result = upload_for_user(name)
    results.append(result)
    print(f"  User: {result['username']}")
    print(f"    upload_options folder: {result['upload_options_folder']}")
    print(f"    Cloudinary public_id:  {result['cloudinary_public_id']}")
    print(f"    Cloudinary URL:        {result['cloudinary_url']}")
    print()

folders = {r["upload_options_folder"] for r in results}
public_ids = {r["cloudinary_public_id"] for r in results}

if len(folders) == 2 and len(public_ids) == 2:
    print("PASS: entrambi gli utenti hanno cartelle e public_id distinti.")
else:
    print("FAIL: percorsi non distinti tra utenti!")
    raise SystemExit(1)

for result in results:
    expected_prefix = f"JamSession Lab/{result['username']}/gallery"
    if expected_prefix not in result["cloudinary_public_id"]:
        print(
            f"FAIL: public_id non contiene il prefisso atteso per {result['username']}"
        )
        raise SystemExit(1)

print("PASS: i public_id contengono i prefissi username corretti.")

print("\n=== HomeCarouselSlide (percorso fisso) ===")
from pages.models import HomeCarouselSlide
from pages.upload_paths import home_carousel_upload_path

class DummySlide:
    pk = 1

path = home_carousel_upload_path(DummySlide(), "carousel-test.jpg")
print(f"  home_carousel_upload_path: {path}")
assert path == "JamSession Lab/site/home_carousel/carousel-test.jpg"
print("PASS: percorso carosello fisso corretto.")
