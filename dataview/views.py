from django.shortcuts import render, redirect, reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib import messages
from dataview.models import FileMetaData
from django.conf import settings
from django.http import JsonResponse
from django.db import transaction, DatabaseError
import psycopg2 as postgre
import pandas as pd
import datetime
import json
import re
import django.apps

# Global Constants
regExp = "[@!#$%^&*()<>?/\|}{~:-]" # all special characters except for underscore
csvToPostgreObjMap = {
    'object': 'varchar',
    'int64': 'int',
    'float64': 'float',
    'datetime64': 'timestamp',
    'timedelta64[ns]': 'varchar'
}
copy_statement = """
                COPY {tableName} FROM STDIN WITH
                CSV
                HEADER
                DELIMITER AS ','
                """
fetch_statement = "SELECT {opName}({colName}) FROM {tableName}"
fetch_for_plot = "SELECT {colOneName}, {colTwoName} FROM {tableName}"
column_metadata_statement = "SELECT data_type FROM information_schema.columns WHERE table_name = '{tableName}' AND column_name = '{colName}'"

# Create your views here.

def homePage(request):
    print(django.apps.apps.get_models())
    print("autocreated")
    print(print(django.apps.apps.get_models(include_auto_created=True, include_swapped=True)))
    return render(request, 'home.html')

def dataPage(request):
    all_rows = FileMetaData.objects.all()
    context = {'metaDataRows':all_rows}
    return render(request, 'data.html', context)

def plotData(request):
    data_sets = {}
    if request.method == "GET":
        data = FileMetaData.objects.all()
        if len(data) != 0:
            for record in data:
                data_sets[record.table_name] = record.column_headers.split(", ")

    print('Data set names and column headers dict = '+str(data_sets))
    js_sets = json.dumps(data_sets)
    return render(request, 'plot.html', {'datasets':js_sets})

def uploadCSV(request):
    if request.method == "POST":
        fileName = request.POST.get('newFileName')
        csv_file = request.FILES['csvFile']
        print(' initial file type = '+str(type(csv_file)))
        toCleanData = True if request.POST.get('cleanData') == "on" else False 

        if not isFileCSV(csv_file):
            return redirect(reverse('data-page'))

        table_name = cleanString(fileName)
    
        # if existing table name, return message
        existing_table = FileMetaData.objects.filter(table_name=table_name)
        if(len(existing_table)!=0):
            messages.error(request, 'Data exists already with same file name, please change the name or upload different data')
            return redirect(reverse('data-page'))

        # reading the uploaded csv file
        df = pd.read_csv(csv_file)
        print(df.head())

        df.columns = [cleanString(colName) for colName in df.columns]

        cols_str = ", ".join(col for col in df.columns)

        if toCleanData:
            df = cleanData(df)
        
        # DB connection
        conn = createConnection()
        cursor = conn.cursor()
        print(conn.closed) # if 0 then connection is active

        # get create table query
        create_table_query = getCreateTableQuery(df, table_name)

        # create table
        try:
            cursor.execute(create_table_query)
            conn.commit()
        except (Exception, postgre.DatabaseError) as error:
            print('Exception while creating the table - '+str(error))

        # Insert values 
        copyFileValuesToDB(df, table_name, cursor, conn)

        # close cursor
        cursor.close()
        #close connection
        conn.close()

        storeMetaData(table_name, len(df.columns), cols_str, toCleanData)

        return redirect(reverse('data-page'))

def computeData(request):
    print('before if in computeData')
    if request.method == "POST" and request.is_ajax():
        print('inside computeData')
        data_set = request.POST.get('selectedDataset')
        column_selected = request.POST.get('selectedColumn')
        operation_selected = request.POST.get('selectedOperation')

        conn = createConnection()
        cursor = conn.cursor()
        print(conn.closed) # if 0 then connection is active

        if operation_selected == "SUM":
            # check whether column type is supported
            try:
                cursor.execute(column_metadata_statement.format(tableName=data_set, colName=column_selected))
                queried_datatype = cursor.fetchall()
                conn.commit()
            except (Exception, postgre.DatabaseError) as Error:
                print('Exception while fetching data : '+str(error))

            print('the queried dtatype = '+str(queried_datatype))
            if queried_datatype[0][0] is not None:
                if queried_datatype[0][0] == 'character varying':
                    # data not suitable for operation
                    msg = 'The operation SUM cant be performed on the selected column'
                    return JsonResponse({'messages':msg}, status=200)

        try:
            cursor.execute(fetch_statement.format(opName=operation_selected, colName=column_selected, tableName=data_set))
            queried_result = cursor.fetchall()
            conn.commit()
        except (Exception, postgre.DatabaseError) as Error:
            print('Exception while fetching data : '+str(error))

        print('type if result = '+str(queried_result))

        if queried_result is None:
            messages.error(request, 'No data is found with above conditions, please check the data-set name and column header')
            return redirect(reverse('plot-page'))
        elif operation_selected not in ['MIN', 'MAX', 'SUM']:
            messages.error(request, 'Selected operation is invalid')
            return redirect(reverse('plot-page'))

        
        return JsonResponse({'resultValue':queried_result}, status=200)

def plotGraph(request):
    if request.method == "POST" and request.is_ajax():
        print('Inside the plotGraph')
        data_set = request.POST.get('selectedDataset')
        col1_selected = request.POST.get('selectedColumn1')
        col2_selected = request.POST.get('selectedColumn2')
        range_selected = request.POST.get('selectedRange')
        record_count = request.POST.get('selectedRecordCount')

        conn = createConnection()
        cursor = conn.cursor()

        try:
            cursor.execute(fetch_for_plot.format(colOneName=col1_selected, colTwoName=col2_selected, tableName=data_set))
            fetched_rows = cursor.fetchall()
            conn.commit()
        except (Exception, postgre.DatabaseError) as error:
            print('Exception while quering records for Plot graph - '+error)

        start = 0
        end = len(fetched_rows) - 1
        if range_selected != "All":
            if len(fetched_rows) != 0:
                total_records_count = len(fetched_rows)
                record_count_in_bin = int(total_records_count/3)
                if range_selected == "Initial":
                    end = record_count_in_bin
                elif range_selected == "Intermediate":
                    start = record_count_in_bin
                    end = record_count_in_bin + record_count_in_bin
                elif range_selected == "Final":
                    start = record_count_in_bin + record_count_in_bin

        xValues = []
        yValues = []
        count = 0
        for row in fetched_rows[start:end]:
            xValues.append(row[0])
            yValues.append(row[1])
            count = count + 1
            if range_selected != "All" and record_count != "All" and count == int(record_count):
                break
            

        return_json = {'xValues':xValues, 
                        'yValues':yValues, 
                        'graph-mode':"markers", 
                        'graph-type':"scatter", 
                        'xAxis':col1_selected, 
                        'yAxis':col2_selected,
                        'graphTitle': col1_selected+' vs '+col2_selected
                        }
        return JsonResponse(return_json, status=200)

        
################################################
# Utility Methods

# To check whether it is a csv file
def isFileCSV(csv_file):
    if not csv_file.name.endswith('.csv'):
        messages.add_message(request, messages.ERROR, 'The file uploaded is not a csv file.')
        return False
    return True

# To clean the string such that string doesn't have any special charcaters and to replace space by underscore
# converting all the names to lowercase for storing in DB
def cleanString(strContent):
    tempStr = re.sub(regExp, "", strContent)

    return re.sub(" ", "_", tempStr.lower())

def cleanData(data):
    # removing empty cells from the data
    data.dropna(inplace=True)

    return data

def createConnection():
    # DB connection
    try:
        conn = postgre.connect(dbname="insightful", user="postgres", password="Kasi123$", host = "127.0.0.1", port = "5432")     
    except (Exception, postgre.DatabaseError) as error:
        print('Connection Error - '+str(error))
    
    return conn


# Build query for creating a table
def getCreateTableQuery(df, tableName):
    if df is not None:
        colsWithTypesForQuery = ", ".join("{} {}".format(c,d) for (c, d) in zip(df.columns, df.dtypes.replace(csvToPostgreObjMap)))
        print('in fi '+colsWithTypesForQuery)
        query = 'create table '+tableName+' ('+colsWithTypesForQuery+' )'
        return query
    return ''

# Copy file values to DB
def copyFileValuesToDB(df, table_name, cursor, conn):
    file_loc = settings.MEDIA_ROOT+'/'+table_name+'.csv'
    df.to_csv(file_loc, header=df.columns, index=False, encoding='utf-8')
    # open the csv file to save as object
    data_file = open(file_loc)
    print('the type of file = '+str(type(data_file)))
    # copy data from file to DB
    print('Testing - '+copy_statement.format(tableName=table_name))
    print('connection value - '+str(conn.closed))
    try:
        cursor.copy_expert(sql=copy_statement.format(tableName=table_name), file=data_file)
        conn.commit()
    except (Exception) as error:
        print('Exception while commit to DB : '+str(error))
        conn.rollback()

    # close file
    data_file.close()

def storeMetaData(table_name, cols_count, cols_str, data_cleaned):
    print(datetime.datetime.now())
    try:
        new_obj = FileMetaData.objects.create(table_name=table_name, uploaded_on=datetime.datetime.now(), data_cleaning=data_cleaned, column_headers=cols_str, total_cols=cols_count)
        new_obj.save()
    except (Exception, DatabaseError) as error:
        print('Exception while saving meta data record : '+str(error))
        transaction.rollback()



