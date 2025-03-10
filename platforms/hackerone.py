from config import API
from typing import List
import os
import json

class HackerOneAPI(API):
    def __init__(self, username: str, token: str, progress_dir: str = "./progress", final_file: str = "hackerone.json") -> None:
        super().__init__(base_url='https://api.hackerone.com')
        self.username = username
        self.token = token
        self.session.auth = (self.username, self.token)
        self.progress_dir = progress_dir
        self.final_file = final_file
        if not os.path.exists(self.progress_dir):
            os.makedirs(self.progress_dir)

    def get_last_page(self) -> int:
        """Determina la última página descargada basándose en los archivos existentes."""
        existing_pages = [
            int(f.split("_page")[-1].split(".json")[0])
            for f in os.listdir(self.progress_dir) if f.startswith("hackerone_page")
        ]
        return max(existing_pages) if existing_pages else 0

    async def paginate(self, endpoint: str) -> List[dict]:
        params = {}
        last_page = self.get_last_page()
        all_data = []
        
        current_page = 0
        while True:
            current_page += 1
            if current_page <= last_page:
                continue  # Saltar las páginas ya guardadas

            response_json = await self.get(endpoint, params=params)
            
            # Guardar la página en un archivo
            filename = f"{self.progress_dir}/hackerone_page{current_page}.json"
            with open(filename, "w") as f:
                json.dump(response_json, f, indent=4)
            
            all_data.append(response_json)
            yield response_json

            if 'next' in response_json.get('links', {}):
                endpoint = response_json['links']['next']
            else:
                break
        
        # Una vez finalizada la paginación, consolidar los datos
        self.merge_pages()

    def merge_pages(self):
        """Combina todos los datos paginados en un único archivo y elimina los archivos individuales."""
        all_data = []
        for filename in sorted(os.listdir(self.progress_dir)):
            if filename.startswith("hackerone_page") and filename.endswith(".json"):
                with open(os.path.join(self.progress_dir, filename), "r") as f:
                    all_data.append(json.load(f))
                os.remove(os.path.join(self.progress_dir, filename))
        
        with open(self.final_file, "w") as f:
            json.dump(all_data, f, indent=4)

    async def program_info(self, scope: str) -> dict:
        """
        Gathering information of a scope with hackerone API.

        Args:
            scope (str): HackerOne program scope handle.

        Yields:
            dict: A dictionary representing the response JSON for scope information
        """
        response_json = await self.get(f"{self.base_url}/v1/hackers/programs/{scope}")
        yield response_json