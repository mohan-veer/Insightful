from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import permissions
from .models import FileMetaData
from .serializers import FileMetaDataSerializer
from django.http import JsonResponse
from django.db import transaction, DatabaseError
from django.conf import settings
import psycopg2 as postgre
import pandas as pd
import datetime
import os
import re

# Create your views here.

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
fetch_for_plot  = "SELECT {colOneName}, {colTwoName} FROM {tableName}"
column_metadata_statement = "SELECT data_type FROM information_schema.columns WHERE table_name = '{tableName}' AND column_name = '{colName}'"
fetch_all_statement = "SELECT * FROM {tableName}"
copy_to_csv = "COPY (SELECT * FROM {tableName}) TO STDOUT WITH CSV HEADER DELIMITER AS ',' "

class FileMetaDataView(APIView):

    def get(self, request):
        all_rows = FileMetaData.objects.all()
        serializer = FileMetaDataSerializer(all_rows, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        errors = {}
        result = {}
        newFileName = ''
        toCleanData = False
        
        # Input validation
        if request.data.get('csvFile') is not None:
            if not isFileCSV(request.data.get('csvFile')):
                errors["FILE_TYPE_ERR"] = "The provide file type is not supported, please upload .csv file"
                return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            errors["INVALID_INPUT_ERR"]="Please provide an input file of type .csv"
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        if request.data.get("newFileName") is not None:
            if not isinstance(request.data.get("newFileName"), str):
                errors["INVALID_INPUT_ERR"]="File name should of type string"
                return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        if request.data.get("cleanData") is not None:
            if not isinstance(request.data.get("cleanData"), str):
                errors["INVALID_INPUT_ERR"]="cleanData should be of type string"
                return Response(errors, status=status.HTTP_400_BAD_REQUEST)
            elif request.data.get("cleanData").lower() != "true" and  request.data.get("cleanData").lower() != "false":
                errors["INVALID_INPUT_ERR"]="Boolean value should be provided either true or false"
                return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        
        csv_file = request.data.get('csvFile')

        # if new file name and cleanData are not provided then default values will be taken
        if request.data.get("newFileName") is not None:
            newFileName = request.data.get("newFileName")
        else:
            newFileName = csv_file.name

        if request.data.get('cleanData') is not None:
            toCleanData = request.data.get('cleanData')

        table_name = cleanString(newFileName)

        existing_table = FileMetaData.objects.filter(table_name=table_name)
        if len(existing_table) != 0:
            errors["FILE_UPLOAD_ERR"]="Data already exists with provided fileName, please change data file or provide a new file name"
            return Response(errors, status=status.HTTP_406_NOT_ACCEPTABLE)

        try:
            uploadData(csv_file, toCleanData, table_name)
            result["File Uploaded"] = True
            return Response(result, status=status.HTTP_200_OK)
        except (Exception) as error:
            errors["UNKNOWN_ERR"]="Unknow exception while uploading the data, please contact the adminstrator"
            return Response(errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FileTableView(APIView):

    def get(self, request, tablename):
        errors = {}
        if not isinstance(tablename, str):
            errors["INVALID_INPUT_ERR"]="File name should of type string"
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        table_data = FileMetaData.objects.filter(table_name=tablename)
        if len(table_data) == 0:
            errors["DATA_ERR"]="No data is found with table name : "+tablename
            return Response(errors, status=status.HTTP_404_NOT_FOUND)
        cols = table_data[0].column_headers.split(", ")
        return_json = {}
    
        # DB connection
        conn = createConnection()
        cursor = conn.cursor()
        print(conn.closed) # if 0 then connection is active

        try:
            cursor.execute(fetch_all_statement.format(tableName=tablename))
            queried_rows = cursor.fetchall()
            conn.commit()
        except (Exception, postgre.DatabaseError) as error:
            print('Exception while fetching data : '+str(error))

        for index,col in enumerate(cols):
            return_json[col] = list(list(zip(*queried_rows))[index])

        return Response(return_json, status=status.HTTP_200_OK)
        

class ComputeDataView(APIView):

    def post(self, request, tablename):
        errors = {}
        try:
            columnName = request.data["columnName"]
        except (KeyError) as error:
            print('Exception while reading api data - '+str(error))
            errors["INVALID_INPUT_ERR"]="Missing columnName parameter"
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            operation = request.data["operation"]
        except (KeyError) as error:
            print('Exception while reading api data - '+str(error))
            errors["INVALID_INPUT_ERR"]="Missing operation parameter"
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        if len(columnName) == 0:
            errors["INVALID_INPUT_ERR"]="Please provide a column name to perform the operation"
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        elif len(operation) == 0:
            errors["INVALID_INPUT_ERR"]="Please provide a operation value (SUM, MIN, MAX)"
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        table_data = FileMetaData.objects.filter(table_name=tablename)
        if len(table_data) == 0:
            errors["DATA_ERR"]="No data is found with table name : "+tablename
            return Response(errors, status=status.HTTP_404_NOT_FOUND)

        cols = table_data[0].column_headers.split(", ")

        if columnName not in cols:
            errors["INVALID_INPUT_ERR"]="Column name: {col} is not part of table {table}".format(col=columnName, table=tablename)
            return Response(errors, status=status.HTTP_404_NOT_FOUND)
        elif operation.lower() not in ["min", "max", "sum"]:
            errors["INVALID_INPUT_ERR"]="Provided operation : {op} is not a valid option, please select among - MIN, MAX, SUM".format(op=operation)
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        # DB connection
        conn = createConnection()
        cursor = conn.cursor()
        print(conn.closed) # if 0 then connection is active

        if operation.lower() == "sum":
            if not isColumnValidForOperation(tablename, columnName, cursor, conn):
                errors["INVALID_INPUT_ERR"]="Provided operation {op} cannot be performed on {col} column".format(op=operation, col=columnName)
                return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            cursor.execute(fetch_statement.format(opName=operation,colName=columnName, tableName=tablename))
            queried_rows = cursor.fetchall()
            conn.commit()
        except (Exception, postgre.DatabaseError) as error:
            print('Exception while fetching data : '+str(error))

        return Response({'Result':queried_rows}, status=status.HTTP_200_OK)


class PlotDataView(APIView):
    def get(self, request, tablename):   
        errors = {}
        try:
            columnOne = request.data["columnOne"]
        except (KeyError) as error:
            print('Exception while reading api data - '+str(error))
            errors["INVALID_INPUT_ERR"]="Missing columnOne parameter"
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            columnTwo = request.data['columnTwo']
        except (KeyError) as error:
            print('Exception while reading api data - '+str(error))
            errors["INVALID_INPUT_ERR"]="Missing columnTwo parameter"
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        
    
        table_data = FileMetaData.objects.filter(table_name=tablename)
        if len(table_data) == 0:
            errors["DATA_ERR"]="No data is found with table name : "+tablename
            return Response(errors, status=status.HTTP_404_NOT_FOUND)

        cols = table_data[0].column_headers.split(", ")

        if len(columnOne) == 0 or len(columnTwo) == 0:
            errors["INVALID_INPUT_ERR"]="Both the column names should be provided"
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        elif not isinstance(columnOne, str) or not isinstance(columnTwo, str):
            errors["INVALID_INPUT_ERR"]="Column names should of type string"
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        elif columnOne not in cols:
            errors["INVALID_INPUT_ERR"]="Column name: {col} is not part of table {table}".format(col=columnOne, table=tablename)
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        elif columnTwo not in cols:
            errors["INVALID_INPUT_ERR"]="Column name: {col} is not part of table {table}".format(col=columnTwo, table=tablename)
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        return_json = {}
        cols = [columnOne, columnTwo]    
        # DB connection
        conn = createConnection()
        cursor = conn.cursor()
        print(conn.closed) # if 0 then connection is active

        try:
            cursor.execute(fetch_for_plot.format(colOneName=columnOne,colTwoName=columnTwo, tableName=tablename))
            queried_rows = cursor.fetchall()
            conn.commit()
        except (Exception, postgre.DatabaseError) as error:
            print('Exception while fetching data : '+str(error))

        for index,col in enumerate(cols):
            return_json[col] = list(list(zip(*queried_rows))[index])

        return Response(return_json, status=status.HTTP_200_OK)


        
# Utility Methods

# To check whether it is a csv file
def isFileCSV(csv_file):
    if not csv_file.name.endswith('.csv'):
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
    print('inside copyFielVlauesToDB')
    file_loc = settings.MEDIA_ROOT+'/'+table_name+'.csv'
    print('fiel loc = '+file_loc)
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
    data = {
        'table_name': table_name,
        'uploaded_on': datetime.datetime.now(),
        'last_modified': datetime.datetime.now(),
        'data_cleaning': data_cleaned,
        'column_headers': cols_str,
        'total_cols': cols_count
    }
    try:
        serializer = FileMetaDataSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
    except (Exception, DatabaseError) as error:
        print('Exception while saving meta data record : '+str(error))
        transaction.rollback()

def removeUploadedFile(table_name):
    file_loc = settings.MEDIA_ROOT+'/'+table_name+'.csv'
    try:
        os.remove(file_loc)
    except (Exception) as error:
        print('Exception while deleting a file - '+str(error))


# uploadData
def uploadData(csv_file, toCleanData, table_name):
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

    removeUploadedFile(table_name)

def isColumnValidForOperation(table_name, col_name, cursor, conn):
    # check whether column type is supported
    try:
        cursor.execute(column_metadata_statement.format(tableName=table_name, colName=col_name))
        queried_datatype = cursor.fetchall()
        conn.commit()
    except (Exception, postgre.DatabaseError) as error:
        print('Exception while fetching data : '+str(error))

    if queried_datatype[0][0] is not None:
        if queried_datatype[0][0] == 'character varying':
            return False

    return True


