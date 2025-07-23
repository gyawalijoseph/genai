from bs4 import BeautifulSoup
import json


def extract_data_from_html_table(html_content, file_name):
    """
    Extracts data from an HTML table and returns it as a list of dictionaries.

    Args:
        html_content (str): The HTML content containing the table.
        file_name (str): The name of the file to associate with the extracted data.

    Returns:
        list: A list of dictionaries representing the rows of the table.
    """

    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')

    if not table:
        return []

    headers = [header.text.strip() for header in table.find_all('th')]
    rows = []

    for row in table.find_all('tr')[1:]:  # Skip header row
        cells = row.find_all('td')
        if len(cells) == len(headers):
            row_data = {headers[i]: cells[i].text.strip() for i in range(len(headers))}
            row_data['file_name'] = file_name
            rows.append(row_data)

    return rows