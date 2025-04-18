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
        self.progress_file = os.path.join(progress_dir, "hackerone_progress.json")
        if not os.path.exists(self.progress_dir):
            os.makedirs(self.progress_dir)

    def load_progress(self) -> dict:
        """Load progress from the progress file."""
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {"last_page": 0, "total_pages": None, "programs_processed": []}

    def save_progress(self, progress: dict) -> None:
        """Save progress to the progress file."""
        with open(self.progress_file, 'w') as f:
            json.dump(progress, f, indent=4)

    async def paginate(self, endpoint: str) -> List[dict]:
        progress = self.load_progress()
        params = {}
        current_page = progress["last_page"]
        
        while True:
            current_page += 1
            response_json = await self.get(endpoint, params=params)
            
            # Save the page data
            filename = f"{self.progress_dir}/hackerone_page{current_page}.json"
            with open(filename, "w") as f:
                json.dump(response_json, f, indent=4)
            
            # Update progress
            progress["last_page"] = current_page
            if 'total_pages' in response_json.get('meta', {}):
                progress["total_pages"] = response_json['meta']['total_pages']
            self.save_progress(progress)
            
            yield response_json

            if 'next' in response_json.get('links', {}):
                endpoint = response_json['links']['next']
            else:
                break
        
        # Once pagination is complete, merge the pages
        self.merge_pages()

    def merge_pages(self):
        """Combine all paginated data into a single file and clean up individual files."""
        all_data = []
        progress = self.load_progress()
        
        # Collect all page data
        for page_num in range(1, progress["last_page"] + 1):
            filename = os.path.join(self.progress_dir, f"hackerone_page{page_num}.json")
            if os.path.exists(filename):
                with open(filename, "r") as f:
                    all_data.append(json.load(f))
                os.remove(filename)
        
        # Save the consolidated data
        with open(self.final_file, "w") as f:
            json.dump(all_data, f, indent=4)
        
        # Clear progress file
        if os.path.exists(self.progress_file):
            os.remove(self.progress_file)

    async def program_info(self, scope: str) -> dict:
        """
        Gathering information of a scope with hackerone API.

        Args:
            scope (str): HackerOne program scope handle.

        Yields:
            dict: A dictionary representing the response JSON for scope information
        """
        progress = self.load_progress()
        if scope in progress.get("programs_processed", []):
            return
        
        response_json = await self.get(f"{self.base_url}/v1/hackers/programs/{scope}")
        
        # Update progress
        progress["programs_processed"].append(scope)
        self.save_progress(progress)
        
        yield response_json