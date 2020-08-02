import uuid
import sys
import logging
import pymysql

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def item_mapper(item):
  new_item = {}
  for key, value in item.items():
    new_item[key] = value.get('S')
  return new_item

def prepare_insert_statement(item):
    item.pop('time', None)
    columns_list = list(item.keys())  
    values_list = list(item.values())

    columns = '(' + ','.join(columns_list) + ')'
    values = "('" + "','".join(values_list) + "')"

    insert_statement = f'insert into security_occurrences {columns} values {values}'
    print(insert_statement)
    return insert_statement

def get_db_connection():
    rds_host  = "database-1.cluster-ce35biib1wz2.us-east-1.rds.amazonaws.com"
    name = 'admin'
    password = 'admin123'
    db_name = 'security_occurrences'
    try:
        conn = pymysql.connect(rds_host, user=name, passwd=password, db=db_name, connect_timeout=15)
        return conn
    except pymysql.MySQLError as e:
        logger.error("ERROR: Unexpected error: Could not connect to MySQL instance.")
        logger.error(e)
        sys.exit()

def insert_item(insert_statement, conn):
    with conn.cursor() as cur:
        cur.execute(insert_statement)
        conn.commit()
        cur.execute('select * from security_occurrences where id = (select max(id) from security_occurrences)')
        for row in cur:
            print(row)
        conn.commit()
    return conn

def handler(event, context):
    print(event)

    records = event['Records'][0]
    item = records['dynamodb']['NewImage']
    response = 'success'
    if item.get('status').get('S') in ['NON_COMPLIANT', 'COMPLIANT']:
        try:
            new_item = item_mapper(item)
            insert_statement = prepare_insert_statement(new_item)
            connection = get_db_connection()
            insert_item(insert_statement, connection)
            
            # new_item['DATE_TIME'] = new_item.pop('time')
        except Exception as e:
            print(e)
            return "catched error -> " + str(e)
    return response