import os

def get_code(file_name):
    path = os.getcwd() + '/lambda/'
    file_path = path + file_name
    with open(file_path, 'r') as f:
        file_content = f.read()
        return file_content
