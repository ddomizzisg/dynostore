import argparse
import requests
import os
import logging
from dynostore.utils.hardware import get_default_partition_size, get_total_memory


def registContainer(admin_token, address, memory, storage, verbose=True):
    url = f'http://{os.environ["APIGATEWAY_HOST"]}/datacontainer/{admin_token}'
    data = {"memory": str(memory), "storage": str(storage), "url": address, "up": 1}
    logger.info(f'Sending request to {url} with parameters {data}')

    r = requests.post(url, json=data)

    if r.status_code == 200:
        logger.info('Data container succesfully added')
    else:
        try:
            logger.error(r.json()['message'])
        except:
            logger.error(r.text)


logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M')
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(
    prog='DynoStore datacontainer',
    description='Abstraction to manage the data in DynoStore')

parser.add_argument('admintoken', help="Admin (user) token")
parser.add_argument(
    'address', help="Data container address. Example, http://192.1.1.1:20006/")
parser.add_argument('-s', '--storage', default=get_default_partition_size(),
                    help="Storage in bytes capacity of the data container. By default the storage capacity will be equal to the size of the default parition.")
parser.add_argument('-m', '--memory', default=get_total_memory(),
                    help="Memory in bytes of the host where the data container is deployed. By default, the total amount of memory in the system will be assigned.")
parser.add_argument('-v', '--verbose', action='store_true',
                    default=True, help='Show outputs')

args = parser.parse_args()

registContainer(args.admintoken, args.address,
                args.memory, args.storage, args.verbose)
