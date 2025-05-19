import argostranslate.package
import argostranslate.translate

from_code = "en"
to_code = "es"

# Download and install Argos Translate package
argostranslate.package.update_package_index()
available_packages = argostranslate.package.get_available_packages()
package_to_install = next(
    filter(
        lambda x: x.from_code == from_code and x.to_code == to_code, available_packages
    )
)
argostranslate.package.install_from_path(package_to_install.download())

# Translate
def translate_text(text, from_code, to_code):
    translatedText = argostranslate.translate.translate(text, from_code, to_code)
    return translatedText

# '¡Hola Mundo!'
print(translate_text("Protein Pro", "en", "ar"))

