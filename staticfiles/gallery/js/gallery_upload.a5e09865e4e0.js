document.addEventListener("DOMContentLoaded", () => {
    const fileInput = document.getElementById("id_files");
    const previewContainer = document.getElementById("gallery-upload-preview");
    const previewList = document.getElementById("gallery-upload-preview-list");
    const form = document.getElementById("gallery-upload-form");

    if (!fileInput || !previewContainer || !previewList) {
        return;
    }

    const maxBytes =
        window.JamMediaUploadGuard?.DEFAULT_MAX_BYTES ?? 104_857_600;
    const formatFileSize =
        window.JamMediaUploadGuard?.formatFileSize
        ?? ((bytes) => {
            if (bytes >= 1048576) {
                return `${(bytes / 1048576).toFixed(1)} MB`;
            }
            if (bytes >= 1024) {
                return `${Math.round(bytes / 1024)} KB`;
            }
            return `${bytes} B`;
        });

    const videoIcon = `
        <svg class="gallery-upload-preview__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="m15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z" />
        </svg>`;

    const genericIcon = `
        <svg class="gallery-upload-preview__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
        </svg>`;

    const isLikelyVideo = (file) => file.type.startsWith("video/");

    const isLikelyImage = (file) => file.type.startsWith("image/");

    const renderPreviewItem = (file) => {
        const item = document.createElement("li");
        item.className = "gallery-upload-preview__item";

        const isOverLimit = file.size > maxBytes;
        if (isOverLimit) {
            item.classList.add("gallery-upload-preview__item--error");
        }

        const thumb = document.createElement("div");
        thumb.className = "gallery-upload-preview__thumb";

        if (isLikelyImage(file)) {
            const img = document.createElement("img");
            img.className = "gallery-upload-preview__image";
            img.alt = "";
            const objectUrl = URL.createObjectURL(file);
            img.src = objectUrl;
            img.onload = () => URL.revokeObjectURL(objectUrl);
            thumb.appendChild(img);
        } else if (isLikelyVideo(file)) {
            thumb.innerHTML = videoIcon;
        } else {
            thumb.innerHTML = genericIcon;
        }

        const meta = document.createElement("div");
        meta.className = "gallery-upload-preview__meta";

        const name = document.createElement("p");
        name.className = "gallery-upload-preview__name";
        name.textContent = file.name;

        const size = document.createElement("p");
        size.className = "gallery-upload-preview__size";
        size.textContent = isOverLimit
            ? `${formatFileSize(file.size)} — exceeds 100 MB limit`
            : formatFileSize(file.size);

        meta.appendChild(name);
        meta.appendChild(size);
        item.appendChild(thumb);
        item.appendChild(meta);
        previewList.appendChild(item);
    };

    const updatePreview = () => {
        previewList.replaceChildren();

        const files = Array.from(fileInput.files || []);
        if (!files.length) {
            previewContainer.classList.add("hidden");
            return;
        }

        previewContainer.classList.remove("hidden");
        files.forEach(renderPreviewItem);
    };

    fileInput.addEventListener("change", updatePreview);

    // Refresh preview after the guard strips oversized files.
    if (form) {
        form.addEventListener("mediaupload:filtered", updatePreview);
    }
});
