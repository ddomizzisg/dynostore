import requests

class CatalogController():

    @staticmethod
    def createOrGetCatalog(
        request,
        pubsub: str, 
        catalog: str, 
        tokenuser: str,
        dispersemode: str = "SINGLE",
        encryption: int = 0,
        fathers_token: str = "/",
        processed: int = 0
    ):
        
        url_service = f'http://{pubsub}/catalog/{catalog}/?tokenuser={tokenuser}'
        print(url_service, flush=True)
        data = {
            'dispersemode': dispersemode, 
            'encryption': encryption, 
            'fathers_token': fathers_token, 
            'processed': processed
            }
        results = requests.put(url_service, json=data)
        print(results.text, flush=True)
        if results.status_code == 201 or results.status_code == 302:
            return results.json(), results.status_code
        else:
            return results.text, results.status_code
    
    
    @staticmethod
    def deleteCatalog(
        pubsub: str, 
        catalog: str, 
        tokenuser: str
    ):
        url_service = f'http://{pubsub}/catalog/{catalog}/?tokenuser={tokenuser}'
        results = requests.delete(url_service)
        return results.json(), results.status_code
    
    @staticmethod
    def getCatalog(
        pubsub: str, 
        catalog: str, 
        tokenuser: str
    ):
        url_service = f'http://{pubsub}/catalog/{catalog}/?tokenuser={tokenuser}'
        results = requests.get(url_service)
        return results.json(), results.status_code

    @staticmethod
    def getSubscribedCatalogs(
        pubsub: str, 
        tokenuser: str
    ):
        url_service = f'http://{pubsub}/user/{tokenuser}/catalogs/subscribed'
        results = requests.get(url_service)
        return results.json(), results.status_code

    @staticmethod
    def getSubCatalogs(
        pubsub: str, 
        father: str
    ):
        url_service = f'http://{pubsub}/catalog/{father}/results'
        results = requests.get(url_service)
        return results.json(), results.status_code
    
    @staticmethod
    def registFileInCatalog(
        pubsub: str, 
        catalog: str, 
        tokenuser: str, 
        keyObject: str
    ):
        url_service = f'http://{pubsub}/catalog/{catalog}/object/{keyObject}'
        results = requests.post(url_service)
        print(results.text, flush=True)
        if results.status_code == 201:
            return results.json(), results.status_code
        elif results:
            return results.text, results.status_code
    
    @staticmethod
    def listFilesInCatalog(
        pubsub: str,
        catalog: str,
        tokenuser: str
    ):
        url_service = f'http://{pubsub}/list/catalog/{catalog}'
        print(url_service, flush=True)
        results = requests.get(url_service)
        print(results.text, flush=True)
        return results.json(), results.status_code