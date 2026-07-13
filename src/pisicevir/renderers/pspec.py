import xml.dom.minidom
from pisicevir.models.pisi import PisiRecipe

class PspecRenderer:
    def __init__(self, recipe: PisiRecipe):
        self.recipe = recipe

    def render(self) -> str:
        doc = xml.dom.minidom.Document()
        pisi = doc.createElement("PISI")
        doc.appendChild(pisi)

        # Source
        source = doc.createElement("Source")
        pisi.appendChild(source)
        
        name = doc.createElement("Name")
        name.appendChild(doc.createTextNode(self.recipe.source.name))
        source.appendChild(name)
        
        summary = doc.createElement("Summary")
        summary.appendChild(doc.createTextNode(self.recipe.source.summary))
        source.appendChild(summary)
        
        description = doc.createElement("Description")
        description.appendChild(doc.createTextNode(self.recipe.source.description))
        source.appendChild(description)
        
        # Packager
        packager = doc.createElement("Packager")
        source.appendChild(packager)
        p_name = doc.createElement("Name")
        p_name.appendChild(doc.createTextNode(self.recipe.source.packager.name))
        packager.appendChild(p_name)
        p_email = doc.createElement("Email")
        p_email.appendChild(doc.createTextNode(self.recipe.source.packager.email))
        packager.appendChild(p_email)

        # Packages
        for pkg_model in self.recipe.packages:
            package = doc.createElement("Package")
            pisi.appendChild(package)
            
            p_name = doc.createElement("Name")
            p_name.appendChild(doc.createTextNode(pkg_model.name))
            package.appendChild(p_name)
            
            runtime_deps = doc.createElement("RuntimeDependencies")
            package.appendChild(runtime_deps)
            for dep in pkg_model.runtime_dependencies:
                d = doc.createElement("Dependency")
                d.appendChild(doc.createTextNode(dep.name))
                runtime_deps.appendChild(d)

            files = doc.createElement("Files")
            package.appendChild(files)
            for f_path in pkg_model.files:
                f = doc.createElement("Path")
                f.appendChild(doc.createTextNode(f_path))
                files.appendChild(f)

        # History
        history = doc.createElement("History")
        pisi.appendChild(history)
        for entry in self.recipe.history:
            update = doc.createElement("Update")
            update.setAttribute("release", entry.release)
            history.appendChild(update)
            
            date = doc.createElement("Date")
            date.appendChild(doc.createTextNode(entry.date))
            update.appendChild(date)
            
            version = doc.createElement("Version")
            version.appendChild(doc.createTextNode(entry.version))
            update.appendChild(version)
            
            comment = doc.createElement("Comment")
            comment.appendChild(doc.createTextNode(entry.comment))
            update.appendChild(comment)
            
            h_name = doc.createElement("Name")
            h_name.appendChild(doc.createTextNode(entry.name))
            update.appendChild(h_name)
            
            h_email = doc.createElement("Email")
            h_email.appendChild(doc.createTextNode(entry.email))
            update.appendChild(h_email)

        return doc.toprettyxml(indent="    ")
