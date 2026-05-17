import warnings

# langchain_core/__init__.py calls surface_langchain_deprecation_warnings() on
# import, which resets warnings filters to "default". We must import it first,
# then re-apply our ignore filter so it wins.
import langchain_core  # noqa: F401

warnings.filterwarnings(
    "ignore",
    message="The default value of `allowed_objects` will change",
    category=PendingDeprecationWarning,
)
