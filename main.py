import json
from typing import List
import logging
import os
import asyncio
from config import API
from platforms.hackerone import HackerOneAPI
from platforms.bugcrowd import BugcrowdAPI
from platforms.intigriti import IntigritiAPI
from platforms.yeswehack import YesWeHackAPI
import shutil

class PublicPrograms:
    """A class to retrieve public programs from Platforms."""

    def __init__(self, api: API, platform_name: str) -> None:
        """
        Initialize with API object and platform name.
        """
        self.api = api
        self.platform_name = platform_name
        self.results_directory = './programs'
        self.progress_directory = './progress'
        self.progress_file = f"{self.progress_directory}/{platform_name}.json"
        self.logger = logging.getLogger(self.__class__.__name__)
        self.results: List[dict] = self.load_progress()

    def load_progress(self) -> List[dict]:
        """Load previous progress from a JSON file if it exists."""
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r') as infile:
                return json.load(infile)
        return []

    def save_results(self) -> None:
        """Save results in JSON format."""
        if not os.path.exists(self.results_directory):
            os.makedirs(self.results_directory)
        if not os.path.exists(self.progress_directory):
            os.makedirs(self.progress_directory)
        with open(self.progress_file, 'w') as outfile:
            json.dump(self.results, outfile, indent=4)

    async def get_hackerone_programs(self) -> List[dict]:
        """Retrieve public programs from HackerOne."""
        if self.results:
            self.logger.info(f"Skipping {self.platform_name}, already completed.")
            return self.results

        endpoint = f'{self.api.base_url}/v1/hackers/programs'
        async for response_json in self.api.paginate(endpoint):
            if 'data' in response_json:
                # Only add new programs that haven't been processed yet
                new_programs = [
                    program for program in response_json['data']
                    if program not in self.results
                ]
                self.results.extend(new_programs)
                self.save_results()  # Save progress after each page
            else:
                self.logger.error("Unexpected response format.")
                return []

        # Process program details in smaller batches to avoid timeouts
        batch_size = 10
        for i in range(0, len(self.results), batch_size):
            batch = self.results[i:i + batch_size]
            for scope in batch:
                scope_handle = scope.get('attributes', {}).get('handle')
                if not scope_handle:
                    continue
                    
                async for response_json in self.api.program_info(scope_handle):
                    if 'relationships' in response_json:
                        scope['relationships'] = response_json['relationships']
                        self.save_results()  # Save progress after each program

        return self.results

    async def get_bugcrowd_programs(self) -> List[dict]:
        """Retrieve public programs from Bugcrowd."""
        if self.results:
            self.logger.info(f"Skipping {self.platform_name}, already completed.")
            return self.results

        endpoint = f'{self.api.base_url}/programs.json'
        async for response_json in self.api.paginate(endpoint):
            if 'programs' in response_json:
                self.results.extend(response_json['programs'])

        self.results = [scope for scope in self.results if scope['invited_status'] == 'open']

        for scope in self.results:
            scope_handle = scope.get('code')
            async for response_json in self.api.program_info(scope_handle):
                if 'target_groups' in response_json:
                    scope['target_groups'] = response_json['target_groups']

        self.save_results()
        return self.results

    async def get_yeswehack_programs(self) -> List[dict]:
        """Retrieve public programs from YesWeHack."""
        if self.results:
            self.logger.info(f"Skipping {self.platform_name}, already completed.")
            return self.results

        endpoint = f'{self.api.base_url}/programs'
        async for response_json in self.api.paginate(endpoint):
            if 'items' in response_json:
                self.results.extend(response_json['items'])

        for scope in self.results:
            scope_handle = scope.get('slug')
            async for response_json in self.api.program_info(scope_handle):
                if 'scopes' in response_json:
                    scope['scopes'] = response_json['scopes']

        self.save_results()
        return self.results

    async def get_intigriti_programs(self) -> List[dict]:
        """Retrieve public programs from Intigriti."""
        if self.results:
            self.logger.info(f"Skipping {self.platform_name}, already completed.")
            return self.results

        endpoint = f'{self.api.base_url}/programs'
        response_json = await self.api.get(endpoint)
        if len(response_json) > 0:
            self.results.extend(response_json)

        self.results = [scope for scope in self.results if scope['confidentialityLevel'] == 4 and not scope['tacRequired']]

        for scope in self.results:
            scope_handle = f"{scope.get('companyHandle')}/{scope.get('handle')}"
            async for response_json in self.api.program_info(scope_handle):
                if 'domains' in response_json:
                    scope['domains'] = response_json["domains"][-1]["content"]

        self.save_results()
        return self.results

def clear_dir(directory: str) -> None:
    """Elimina todos los archivos en el directorio temporal."""
    if os.path.exists(directory):
        shutil.rmtree(directory)  # Elimina el directorio y todo su contenido
        os.makedirs(directory)  # Vuelve a crear el directorio vacío

def copy_content(temp_dir: str, final_dir: str) -> None:
    """Copia el contenido del directorio temporal al directorio final."""
    if not os.path.exists(final_dir):
        os.makedirs(final_dir)
    
    # Copiar archivos del directorio temporal al final
    for filename in os.listdir(temp_dir):
        temp_file = os.path.join(temp_dir, filename)
        final_file = os.path.join(final_dir, filename)
        if os.path.isfile(temp_file):
            shutil.copy(temp_file, final_file)  # Copiar archivo individual

async def main():
    """Main function to run the scrapers."""

    try:
        HACKERONE_USERNAME = os.environ['HACKERONE_USERNAME']
        HACKERONE_TOKEN = os.environ['HACKERONE_TOKEN']
    except KeyError:
        raise SystemExit('Please provide the Hackerone username/token.')

    hackerone_api = HackerOneAPI(username=HACKERONE_USERNAME, token=HACKERONE_TOKEN)
    intigriti_api = IntigritiAPI()
    bugcrowd_api = BugcrowdAPI()
    yeswehack_api = YesWeHackAPI()

    public_programs_hackerone = PublicPrograms(api=hackerone_api, platform_name="hackerone")
    public_programs_intigriti = PublicPrograms(api=intigriti_api, platform_name="intigriti")
    public_programs_bugcrowd = PublicPrograms(api=bugcrowd_api, platform_name="bugcrowd")
    public_programs_yeswehack = PublicPrograms(api=yeswehack_api, platform_name="yeswehack")

    await asyncio.gather(
        public_programs_hackerone.get_hackerone_programs(),
        #public_programs_intigriti.get_intigriti_programs(), it changed, to do
        #public_programs_bugcrowd.get_bugcrowd_programs(), it changed, to do
        public_programs_yeswehack.get_yeswehack_programs()
    )

    logging.info("Programs crawled successfully.")

if __name__ == '__main__':
    asyncio.run(main())
    copy_content('./progress', './programs')
    clear_dir('./progress')
