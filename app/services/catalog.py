"""
Motor de Ventas - Catalog and Sales Service
Handles motorcycle catalog queries and sales recommendations.
"""

import logging
from typing import Dict, Any, List, Optional
from google.cloud import firestore

logger = logging.getLogger(__name__)


class MotorVentas:
    """
    Sales engine for motorcycle catalog queries.
    
    Provides information about available motorcycles, specifications,
    and helps customers find their ideal bike based on their needs.
    """
    
    def __init__(self, db: firestore.Client, config_loader=None):
        """
        Initialize the sales motor.
        
        Args:
            db: Firestore client instance
            config_loader: Optional ConfigLoader instance for dynamic catalog
        """
        self._db = db
        self._config_loader = config_loader
        self._catalog = self._load_catalog()
        logger.info("🏍️  MotorVentas initialized")
    
    def _load_catalog(self) -> List[Dict[str, Any]]:
        """
        Load motorcycle catalog from config or use defaults.
        
        Returns:
            List of motorcycle dictionaries
        """
        if self._config_loader:
            try:
                catalog_config = self._config_loader.get_catalog_config()
                return catalog_config.get("items", self._default_catalog())
            except Exception as e:
                logger.error(f"❌ Error loading catalog: {str(e)}")
        
        return self._default_catalog()
    
    def _default_catalog(self) -> List[Dict[str, Any]]:
        """Get default motorcycle catalog."""
        return [
            {
                "id": "nkd-125",
                "name": "NKD 125",
                "category": "urbana",
                "description": "Moto urbana, ideal para ciudad, económica y de bajo consumo",
                "highlights": ["Económica", "Bajo consumo", "Perfecta para ciudad"],
                "active": True
            },
            {
                "id": "sport-100",
                "name": "Sport 100",
                "category": "deportiva",
                "description": "Deportiva de entrada, perfecta para jóvenes que buscan estilo",
                "highlights": ["Deportiva", "Diseño moderno", "Para jóvenes"],
                "active": True
            },
            {
                "id": "victory-black",
                "name": "Victory Black",
                "category": "ejecutiva",
                "description": "Elegante y potente, ideal para ejecutivos y profesionales",
                "highlights": ["Elegante", "Potente", "Ejecutiva"],
                "active": True
            },
            {
                "id": "mrx-150",
                "name": "MRX 150",
                "category": "todo-terreno",
                "description": "Todo terreno, aventurera, resistente y versátil",
                "highlights": ["Aventurera", "Resistente", "Versátil"],
                "active": True
            }
        ]
    
    def buscar_moto(self, texto: str) -> str:
        """
        Search for motorcycles based on user query.
        
        Args:
            texto: User message containing search query
        
        Returns:
            Formatted response with motorcycle recommendations
        """
        try:
            texto_lower = texto.lower()
            
            # Check for specific motorcycle mentions
            motos_mencionadas = []
            for moto in self._catalog:
                if moto["name"].lower() in texto_lower or moto["id"] in texto_lower:
                    motos_mencionadas.append(moto)
            
            # If specific bikes mentioned, show those
            if motos_mencionadas:
                return self._format_motos_response(motos_mencionadas, "encontradas")
            
            # Category-based search
            if any(word in texto_lower for word in ["ciudad", "urbana", "trabajo", "económica"]):
                motos_filtradas = [m for m in self._catalog if m["category"] == "urbana"]
                return self._format_motos_response(motos_filtradas, "para ciudad")
            
            elif any(word in texto_lower for word in ["deportiva", "joven", "rápida", "sport"]):
                motos_filtradas = [m for m in self._catalog if m["category"] == "deportiva"]
                return self._format_motos_response(motos_filtradas, "deportivas")
            
            elif any(word in texto_lower for word in ["ejecutiva", "elegante", "profesional"]):
                motos_filtradas = [m for m in self._catalog if m["category"] == "ejecutiva"]
                return self._format_motos_response(motos_filtradas, "ejecutivas")
            
            elif any(word in texto_lower for word in ["aventura", "terreno", "campo", "montaña"]):
                motos_filtradas = [m for m in self._catalog if m["category"] == "todo-terreno"]
                return self._format_motos_response(motos_filtradas, "todo terreno")
            
            # Default: show all catalog
            else:
                return self._format_catalog_complete()
                
        except Exception as e:
            logger.error(f"❌ Error searching motorcycles: {str(e)}")
            return "Lo siento, hubo un error al buscar motos. Por favor intenta nuevamente."
    
    def _format_motos_response(self, motos: List[Dict[str, Any]], categoria: str) -> str:
        """
        Format motorcycle list into a response string.
        
        Args:
            motos: List of motorcycle dictionaries
            categoria: Category description
        
        Returns:
            Formatted response string
        """
        if not motos:
            return self._format_catalog_complete()
        
        response = f"🏍️ **Motos {categoria}**\n\n"
        
        for moto in motos:
            response += f"**{moto['name']}**\n"
            response += f"📝 {moto['description']}\n"
            response += f"✨ {', '.join(moto['highlights'])}\n\n"
        
        response += "💳 ¿Te gustaría una simulación de crédito para alguna de estas motos?\n"
        response += "📱 También puedo darte más información sobre cualquiera de ellas."
        
        return response.strip()
    
    def _format_catalog_complete(self) -> str:
        """
        Format complete catalog response.
        
        Returns:
            Formatted catalog string
        """
        response = "🏍️ **Catálogo Tienda Las Motos**\n\n"
        response += "Tenemos estas increíbles opciones para ti:\n\n"
        
        for moto in self._catalog:
            if moto.get("active", True):
                response += f"**{moto['name']}** - {moto['description']}\n"
        
        response += "\n💡 Dime qué tipo de moto buscas o pregúntame por alguna específica.\n"
        response += "💳 También puedo hacer una simulación de crédito personalizada."
        
        return response.strip()
    
    def get_moto_by_name(self, nombre: str) -> Optional[Dict[str, Any]]:
        """
        Get motorcycle details by name.
        
        Args:
            nombre: Motorcycle name
        
        Returns:
            Motorcycle dictionary or None if not found
        """
        nombre_lower = nombre.lower()
        for moto in self._catalog:
            if moto["name"].lower() == nombre_lower or moto["id"] == nombre_lower:
                return moto
        return None
