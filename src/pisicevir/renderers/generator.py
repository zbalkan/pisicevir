import os
import yaml
from pisicevir.models.pisi import PisiRecipe, PisiSource, PisiPackager, PisiPackage, PisiHistoryEntry, PisiDependency
from pisicevir.renderers.pspec import PspecRenderer
from pisicevir.renderers.actions import ActionsRenderer

class RecipeGenerator:
    def __init__(self, metadata: dict, payload: list, plan: dict, output_dir: str):
        self.metadata = metadata
        self.payload = payload
        self.plan = plan
        self.output_dir = output_dir

    def generate(self):
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Create recipe model
        recipe = self._create_recipe_model()
        
        # Render pspec.xml
        pspec_renderer = PspecRenderer(recipe)
        with open(os.path.join(self.output_dir, "pspec.xml"), "w") as f:
            f.write(pspec_renderer.render())
            
        # Render actions.py
        actions_renderer = ActionsRenderer(self.plan)
        with open(os.path.join(self.output_dir, "actions.py"), "w") as f:
            f.write(actions_renderer.render())
            
        # Create metadata directory
        metadata_dir = os.path.join(self.output_dir, "metadata")
        os.makedirs(metadata_dir, exist_ok=True)
        
        return self.output_dir

    def _create_recipe_model(self) -> PisiRecipe:
        pkg_name = self.metadata.get("Package", "unknown")
        
        source = PisiSource(
            name=pkg_name,
            summary=self.metadata.get("Description", "").split("\n")[0],
            description=self.metadata.get("Description", ""),
            packager=PisiPackager(name="Pisicevir", email="pisicevir@example.com")
        )
        
        # Map dependencies from plan or metadata
        runtime_deps = []
        if "dependencies" in self.plan and "map" in self.plan["dependencies"]:
            for dep_name in self.plan["dependencies"]["map"].values():
                runtime_deps.append(PisiDependency(name=dep_name))
        
        package = PisiPackage(
            name=pkg_name,
            runtime_dependencies=runtime_deps,
            files=self.payload
        )
        
        history = [
            PisiHistoryEntry(
                version=self.metadata.get("Version", "1.0"),
                release="1",
                date="2023-01-01",
                name="Pisicevir",
                email="pisicevir@example.com",
                comment="Generated from Debian package"
            )
        ]
        
        return PisiRecipe(
            source=source,
            packages=[package],
            history=history
        )
