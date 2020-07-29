def get_string_code(file_name):
    with open(file_name, 'r') as f:
        file_content = f.read()
        return file_content