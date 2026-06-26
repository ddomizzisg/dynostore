import psycopg2
import os
import hashlib
import time
import random


def createToken():
    # Create hashing instance
    hashing = hashlib.sha3_256()

    # Get current timestamp in miliseconds
    timestamps = time.time()

    # Get a random number
    random_Number = random.randint(0, 1000000000)

    # Create a token
    base_str = str(timestamps) + str(random_Number)
    base_str = base_str.encode('utf-8')

    # Hash the token
    hashing.update(base_str)
    token = hashing.hexdigest()
    return token


conn = psycopg2.connect(database=os.environ['POSTGRES_DB'],
                        host="localhost",
                        user=os.environ['POSTGRES_USER'],
                        password=os.environ['POSTGRES_PASSWORD'],
                        port=int(os.environ.get('DB_PORT', 5432)))

try:
    cursor = conn.cursor()

    query_org = "INSERT INTO hierarchy(keyhierarchy, acronym, fullname,tokenhierarchy, father) VALUES (%s, %s, %s, %s, %s);"
    token_org = createToken()
    keyhierarchy = createToken()[:100]
    acronym = "dynostore"
    fullname = "dynostore"
    father = "/"

    cursor.execute(query_org, (keyhierarchy, acronym,
                   fullname, token_org, father))

    query = "INSERT INTO USERS(keyuser,username,email,password,tokenuser,tokenorg,access_token,apikey,isactive,isadmin) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    tokenuser = createToken()
    access_token = createToken()
    apikey = createToken()
    keyuser = createToken()
    username = os.environ['ADMIN_USER']
    password = os.environ['ADMIN_PASSWORD']
    email = os.environ['ADMIN_EMAIL']

    result = cursor.execute(query, (keyuser, username, email, password,
                   tokenuser, token_org, access_token, apikey, True, True))
    conn.commit()
    print(f"User created correctly with token {tokenuser}")
except (Exception, psycopg2.DatabaseError) as error:
    print(error)
