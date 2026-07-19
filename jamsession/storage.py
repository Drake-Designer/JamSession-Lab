from whitenoise.storage import CompressedManifestStaticFilesStorage


class NonStrictStaticFilesStorage(CompressedManifestStaticFilesStorage):
    manifest_strict = False
