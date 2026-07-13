from typing import Dict, Any, List

class Classifier:
    def __init__(self, metadata: Dict[str, Any], payload: List[str]):
        self.metadata = metadata
        self.payload = payload

    def classify(self) -> Dict[str, Any]:
        reasons = []
        warnings = []
        
        # Simple heuristic classification
        has_elf = any(f.endswith((".so", ".so.1")) or "bin/" in f for f in self.payload)
        has_service = any("systemd" in f or "init.d" in f for f in self.payload)
        
        if has_service:
            conv_class = "D"
            policy = "service-sysvinit"
            reasons.append("Contains service-related files")
        elif has_elf:
            conv_class = "B"
            policy = "deb-library"
            reasons.append("Contains ELF executables or libraries")
        else:
            conv_class = "A"
            policy = "deb-data"
            reasons.append("No executables or services detected")
            
        return {
            "package": self.metadata.get("Package", "unknown"),
            "source_type": "deb",
            "conversion_class": conv_class,
            "policy_family": policy,
            "confidence": "medium",
            "reasons": reasons,
            "warnings": warnings
        }
