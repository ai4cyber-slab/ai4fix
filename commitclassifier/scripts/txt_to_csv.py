import os
import csv
from labels import *


LABEL_NUM = 4
PR_NUM = '448'
REPO = 'storm'
RUN_TYPE = 'skipping_tests+interfaces'
FOLDER_PATH = f'Logs/{RUN_TYPE}/{REPO}/{LABEL_NUM}_label/txt_logs/final'


for filename in os.listdir(FOLDER_PATH):

    file_path = os.path.join(FOLDER_PATH, filename)
    model = file_path.split('/')[-1].split('_')[0]
    csv_file = f'Logs/{RUN_TYPE}/{REPO}/{LABEL_NUM}_label/csv_logs/{filename}.csv'

    # Read the text file and split lines
    with open(file_path, 'r') as infile:
        lines = infile.readlines()


    # Strip newline characters and split by ' ' delimiter
    data = [line.strip().split(' ') for line in lines]

    header = ['Repo', 'PR', 'Model', 'Diff number', 'Category', 'Class label', 'Output', 'Stat', 'Reason']

    struts_categories = []
    with open(f'scripts/struts_cats.csv', mode='r') as file:
        reader = csv.reader(file)
        next(reader)
        for row in reader:
            struts_categories.append(row)

    storm_categories = []
    with open(f'scripts/storm_cats.csv', mode='r') as file:
        reader = csv.reader(file)
        next(reader)
        for row in reader:
            storm_categories.append(row)

    with open(csv_file, 'w', newline='') as outfile:
        writer = csv.writer(outfile)
        writer.writerow(header)
        row = []
        row.append(REPO)
        row.append(PR_NUM)
        row.append(model)
        index = 0
        for line in data:
            # if line[0] == 'Repo:' and line[1] == 'struts':
                # labels = struts_labels()
                # categories = struts_categories
                
            # elif line[0] == 'Repo:' and line[1] == 'storm':
            labels = storm_labels()
            categories = storm_categories
                
            if line[0] == 'Diff' and line[1] == 'number:':
                index = int(line[2])
                row.append(line[2])
                row.append(categories[index - 1][1])
                row.append(categories[index - 1][0])

            if line[0] == '"security_relevancy":':
                # output = line[1].replace('"', '').replace(',', '')
                # if output.lower() == 'yes':
                    # label = 'security'
                # else:
                    # label = 'not'

                label = line[1].replace('"', '').replace(',', '').split('_')[0]
                row.append(label)

                if labels[index] == 'security':
                    if label == 'security':
                        row.append('TP')
                    else:
                        row.append('FN')

                if labels[index] == 'not':
                    if label == 'not':
                        row.append('TN')
                    else:
                        row.append('FP')

            if line[0] == '"reason":':
                tmp = line[1:]
                tmp[0] = tmp[0].replace('"', '')
                tmp[-1] = tmp[-1].replace('",', '')
                reason = ''
                for word in tmp:
                    reason += word + ' '
                row.append(reason)
            
            if len(row) == 9:
                writer.writerow(row)
                row = row[:3]


        print(f'Converted "{file_path}" to "{csv_file}" successfully.\n')
