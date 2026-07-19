from whitenoise.storage import CompressedManifestStaticFilesStorage


class NonStrictStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """WhiteNoise storage that tolerates missing CSS/JS referenced assets.

    django-unfold (and some vendor bundles) ship stylesheets that reference
    files not present in the published package. Django's manifest storage
    raises during collectstatic post-processing; we skip those errors so the
    build can finish. Compression and hashing still apply to everything else.
    """

    manifest_strict = False

    def post_process(self, *args, **kwargs):
        for name, hashed_name, processed in super().post_process(*args, **kwargs):
            if isinstance(processed, Exception):
                # Missing referenced file (font, source map, …) — skip, do not fail.
                yield name, hashed_name, False
            else:
                yield name, hashed_name, processed

    def compress_files(self, paths):
        # django-cloudinary-storage's collectstatic may skip copying unhashed
        # files into STATIC_ROOT; only compress paths that actually exist.
        existing_paths = [path for path in paths if self.exists(path)]
        yield from super().compress_files(existing_paths)
