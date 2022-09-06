from django.shortcuts import render, redirect, reverse
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction, DatabaseError
from dataview_api.models import FileMetaData
from dataview_api import views as api_views
import psycopg2 as postgre
from pathlib import Path
import json
import os

# Create your views here.

def homePage(request):
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

        if not api_views.isFileCSV(csv_file):
            return redirect(reverse('data-page'))

        table_name = api_views.cleanString(fileName)
    
        # if existing table name, return message
        existing_table = FileMetaData.objects.filter(table_name=table_name)
        if(len(existing_table)!=0):
            messages.error(request, 'Data exists already with same file name, please change the name or upload different data')
            return redirect(reverse('data-page'))

        api_views.uploadData(csv_file, toCleanData, table_name)

        return redirect(reverse('data-page'))

def computeData(request):
    if request.method == "POST" and request.is_ajax():
        print('inside computeData')
        data_set = request.POST.get('selectedDataset')
        column_selected = request.POST.get('selectedColumn')
        operation_selected = request.POST.get('selectedOperation')

        conn = api_views.createConnection()
        cursor = conn.cursor()
        print(conn.closed) # if 0 then connection is active

        if operation_selected.lower() not in ['min', 'max', 'sum']:
            messages.error(request, 'Selected operation is invalid')
            return redirect(reverse('plot-page'))
        elif operation_selected.lower() == "sum":
            if not api_views.isColumnValidForOperation(data_set, column_selected, cursor, conn):
                msg = 'The operation SUM cant be performed on the selected column'
                return JsonResponse({'messages':msg}, status=200)
         
        try:
            cursor.execute(api_views.fetch_statement.format(opName=operation_selected, colName=column_selected, tableName=data_set))
            queried_result = cursor.fetchall()
            conn.commit()
        except (Exception, postgre.DatabaseError) as Error:
            print('Exception while fetching data : '+str(error))

        if queried_result is None:
            messages.error(request, 'No data is found with above conditions, please check the data-set name and column header')
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

        conn = api_views.createConnection()
        cursor = conn.cursor()

        try:
            cursor.execute(api_views.fetch_for_plot.format(colOneName=col1_selected, colTwoName=col2_selected, tableName=data_set))
            fetched_rows = cursor.fetchall()
            conn.commit()
        except (Exception, postgre.DatabaseError) as error:
            print('Exception while quering records for Plot graph - '+error)
        print(len(fetched_rows))
        start = 0
        end = len(fetched_rows)
        print('end = '+str(end))
        if range_selected != "All":
            if len(fetched_rows) != 0:
                total_records_count = len(fetched_rows)
                record_count_in_bin = int(total_records_count/3)
                if range_selected == "Initial":
                    end = record_count_in_bin
                    print('end = '+str(end))
                elif range_selected == "Intermediate":
                    start = record_count_in_bin
                    end = record_count_in_bin + record_count_in_bin
                    print('start = '+str(start))
                    print('end = '+str(end))
                elif range_selected == "Final":
                    start = record_count_in_bin + record_count_in_bin
                    print('start = '+str(start))

        xValues = []
        yValues = []
        count = 0
        for row in fetched_rows[start:end]:
            xValues.append(row[0])
            yValues.append(row[1])
            count = count + 1
            if range_selected != "All" and record_count != "All" and count == int(record_count):
                break
            
        print(len(xValues))
        print(len(yValues))
        return_json = {'xValues':xValues, 
                        'yValues':yValues, 
                        'graph-mode':"markers", 
                        'graph-type':"scatter", 
                        'xAxis':col1_selected, 
                        'yAxis':col2_selected,
                        'graphTitle': col1_selected+' vs '+col2_selected
                        }
        return JsonResponse(return_json, status=200)

def downloadCSV(request):
    if request.method == "GET" and request.is_ajax():
        table_name = request.GET.get('tableName')
        conn = api_views.createConnection()
        cursor = conn.cursor()

        try:
            downloads_path = str(Path.home() / "Downloads") + "/{tableName}.csv".format(tableName=table_name)
            with open(downloads_path, "w") as file:
                cursor.copy_expert(api_views.copy_to_csv.format(tableName=table_name), file)
                conn.commit()
                file.close()
        except (Exception, postgre.DatabaseError) as error:
            print('Exception while downloading the file - '+str(error))
            
        return JsonResponse({'status':'File is downloaded, please check downloads folder'}, status=200)