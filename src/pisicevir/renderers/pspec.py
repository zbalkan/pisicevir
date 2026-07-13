from __future__ import annotations

import xml.dom.minidom
from typing import Optional

from pisicevir.models.pisi import PisiDependency, PisiRecipe


class PspecRenderer:
    def __init__(self, recipe: PisiRecipe):
        self.recipe = recipe
        self.doc = xml.dom.minidom.Document()

    def render(self) -> str:
        pisi = self.doc.createElement("PISI")
        self.doc.appendChild(pisi)

        source = self.doc.createElement("Source")
        pisi.appendChild(source)
        self._text(source, "Name", self.recipe.source.name)
        self._text(source, "Homepage", self.recipe.source.homepage)

        packager = self.doc.createElement("Packager")
        source.appendChild(packager)
        self._text(packager, "Name", self.recipe.source.packager.name)
        self._text(packager, "Email", self.recipe.source.packager.email)

        for license_name in self.recipe.source.licenses:
            self._text(source, "License", license_name)

        self._text(source, "Summary", self.recipe.source.summary)
        self._text(source, "Description", self.recipe.source.description)

        archive = self.doc.createElement("Archive")
        archive.setAttribute("type", self.recipe.source.archive.archive_type)
        archive.setAttribute("sha1sum", self.recipe.source.archive.sha1sum)
        archive.setAttribute("sha256sum", self.recipe.source.archive.sha256sum)
        archive.appendChild(self.doc.createTextNode(self.recipe.source.archive.uri))
        source.appendChild(archive)

        if self.recipe.source.build_dependencies:
            dependencies = self.doc.createElement("BuildDependencies")
            source.appendChild(dependencies)
            for dependency in self.recipe.source.build_dependencies:
                dependencies.appendChild(self._dependency(dependency))

        for package_model in self.recipe.packages:
            package = self.doc.createElement("Package")
            pisi.appendChild(package)
            self._text(package, "Name", package_model.name)
            if package_model.summary:
                self._text(package, "Summary", package_model.summary)
            if package_model.description:
                self._text(package, "Description", package_model.description)

            if package_model.runtime_dependencies:
                runtime_dependencies = self.doc.createElement("RuntimeDependencies")
                package.appendChild(runtime_dependencies)
                for dependency in package_model.runtime_dependencies:
                    runtime_dependencies.appendChild(self._dependency(dependency))

            files = self.doc.createElement("Files")
            package.appendChild(files)
            for file_path in package_model.files:
                path = self.doc.createElement("Path")
                path.setAttribute("fileType", file_path.file_type)
                path.appendChild(self.doc.createTextNode(file_path.path))
                files.appendChild(path)

        history = self.doc.createElement("History")
        pisi.appendChild(history)
        for entry in self.recipe.history:
            update = self.doc.createElement("Update")
            update.setAttribute("release", entry.release)
            history.appendChild(update)
            self._text(update, "Date", entry.date)
            self._text(update, "Version", entry.version)
            self._text(update, "Comment", entry.comment)
            self._text(update, "Name", entry.name)
            self._text(update, "Email", entry.email)

        return self.doc.toprettyxml(indent="    ", encoding="utf-8").decode("utf-8")

    def _text(self, parent: xml.dom.minidom.Element, name: str, value: str) -> None:
        element = self.doc.createElement(name)
        element.appendChild(self.doc.createTextNode(value))
        parent.appendChild(element)

    def _dependency(self, dependency: PisiDependency) -> xml.dom.minidom.Element:
        element = self.doc.createElement("Dependency")
        if dependency.version:
            element.setAttribute("version", dependency.version)
        if dependency.release:
            element.setAttribute("release", dependency.release)
        element.appendChild(self.doc.createTextNode(dependency.name))
        return element
