from cloudinary.models import CloudinaryField


class DynamicCloudinaryField(CloudinaryField):
    """
    CloudinaryField that merges per-instance upload options from the model.

    If the model defines upload_options(self), those values are applied on
    every upload (in pre_save), with access to the specific instance.
    """

    def pre_save(self, model_instance, add):
        dynamic_options = {}
        if hasattr(model_instance, "upload_options"):
            dynamic_options = model_instance.upload_options() or {}

        if not dynamic_options:
            return super().pre_save(model_instance, add)

        original_options = self.options.copy()
        try:
            self.options = {**original_options, **dynamic_options}
            return super().pre_save(model_instance, add)
        finally:
            self.options = original_options
