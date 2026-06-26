import requests
import json


class DataContainerController():
    @staticmethod
    async def regist(request, admintoken: str, metadataService: str):
        url_to_regist = f"http://{metadataService}/servers/{admintoken}"
        print(url_to_regist, flush=True)

        json_data = await request.json  

        # If you are using `requests` (blocking), it's OK for now
        r = requests.post(url_to_regist, json=json_data)

        print(r.status_code, flush=True)
        print(r.text, flush=True)
        return r.text

    @staticmethod
    async def delete_all(request, admintoken: str, metadataService: str):
        url_to_regist = f"http://{metadataService}/servers/delete/{admintoken}"
        print(url_to_regist, flush=True)
        r = requests.get(url_to_regist)
        print(r.status_code, flush=True)
        print(r.text, flush=True)
        return r.text