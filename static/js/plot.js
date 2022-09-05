var globalData = {}
$(document).ready(function(){
    console.log('inside plot js');
    // retrieving data for plot
    console.log('the data is = '+datasets);
    for(let key in datasets){
        $('#inputDataSet').append('<option> '+key+' </option>');
        $('#inpDataSet').append('<option> '+key+' </option>');
    }
    console.log('type of object = '+typeof datasets);
    globalData = JSON.parse(JSON.stringify(datasets));

    if(globalData.length !=0 ){
        computeOps = ['MIN', 'MAX', 'SUM'];
        for(let op of computeOps){
            $('#inputOperation').append('<option> '+op+' </option>');
        }
        plotOps = ['Initial', 'Intermediate', 'Final', 'All'];
        for(let op of plotOps){
            $('#range').append('<option> '+op+' </option>');
        }
        recordOps = ['25', '50', '75', '100', 'All'];
        for(let op of recordOps){
            $('#recordCount').append('<option> '+op+' </option>');
        }
    }

    // get column names for compute
    $('#selectDiv1').on('change', 'select', function(){
        if(globalData != null){
            dataSelected = $('#inputDataSet').val();
            colValues = globalData[dataSelected];
            if(colValues != null){
                for(let col of colValues){
                    $('#inputColumns').append('<option> '+col+' </option>');
                }
            }
        }
    });   

    // get column names for plot
    $('#selectDiv2').on('change', 'select', function(){
        if(globalData != null){
            dataSelected = $('#inpDataSet').val();
            colValues = globalData[dataSelected];
            if(colValues != null){
                for(let col of colValues){
                    $('#inputColumn1').append('<option> '+col+' </option>');
                }
            }
        }
    }); 

    //remove selected option in other column options
    $('#colOne').on('change', 'select', function(){
        if(globalData != null){
            colValues = globalData[dataSelected];
            optionToRemove = $('#inputColumn1').val();
            $('#inputColumn2').find("option").remove(); //removing existing options before appending
            if(colValues != null){
                for(let col of colValues){
                    if(col != optionToRemove){
                        $('#inputColumn2').append('<option> '+col+' </option>');
                    }
                }
            }
        }
    });

    $('#inputColumn2').on('click', function(){
        if($('#inputColumn1').val() == 'Choose...'){
            alert("Please select column 1 first");
        }
    });

    // if all records to be selected then last option to be diabaled
    $('#range').on('change', function(){
        if($('#range').val() == 'All'){
            $('#recordCount').attr('disabled', true);
            $('#recordCount').val('');
        }
        else{
            $('#recordCount').removeAttr('disabled', true);
        }
    });

    // csrf token
    const csrftoken = Cookies.get('csrftoken');

    // ajax for POST - Compute
    $(document).on('submit','#formPost', function(e){
       
        console.log('data = '+$('#inputDataSet').val());
        console.log('col = '+$('#inputColumns').val());
        console.log('op = '+$('#inputOperation').val());
        if ($('#inputDataSet').val() == 'Choose...' || $('#inputColumns').val() == 'Choose...' || $('#inputOperation').val() == 'Choose...'){
            alert("Please select all the values");
        }
        else{
            console.log('inside else part');
            e.preventDefault(); // prevents page from reloading
            $.ajax({
                type: 'POST',
                url: 'compute/',
                data: {
                    selectedDataset:$('#inputDataSet').val(),
                    selectedColumn:$('#inputColumns').val(),
                    selectedOperation:$('#inputOperation').val(),
                    csrfmiddlewaretoken:csrftoken
                },
                success: function(response){
                    console.log('indise success function = '+response["resultValue"]);
                    console.log('indise success function 1 = '+response["messages"]);
                    if(response["resultValue"] != null){
                        $('#result').val(response["resultValue"]);
                    }
                    else if(response["messages"] != null){
                        $('#result').val('');
                        $('#alertMsg').removeClass('d-none');
                        $('#alertMsg').text(response["messages"]);
                        setTimeout(function() {
                            $('#alertMsg').addClass('d-none');
                        }, 4000);
                        
                    }
                },
                error: function(jqXHR, textStatus, errorText){
                    console.log('the err text = '+errorText);
                }
            });
        }
    });


    // ajax for POST - Plot
    $(document).on('submit', '#formPlot', function(e){
        if ($('#inpDataSet').val() == 'Choose...' || $('#inputColumn1').val() == 'Choose...' || $('#inputColumn2').val() == 'Choose...' || $('#range').val() == 'Choose...'){
            alert("Please select all the values");
        }
        else{
            e.preventDefault();
            $.ajax({
                type:'POST',
                url: 'graph/',
                data:{
                    selectedDataset:$('#inpDataSet').val(),
                    selectedColumn1:$('#inputColumn1').val(),
                    selectedColumn2:$('#inputColumn2').val(),
                    selectedRange:$('#range').val(),
                    selectedRecordCount:$('#recordCount').val(),
                    csrfmiddlewaretoken:csrftoken
                },
                success: function(response){
                    console.log('Inside the success');
                    console.log('mode = '+response['graph-mode']);
                    var data = [{
                        x: response['xValues'],
                        y: response['yValues'],
                        type:response['graph-type'],
                        mode:response['graph-mode']
                      }];
                
                      var layout = {
                        autosize: false,
                        width: 1000,
                        height: 700,
                        xaxis: {title: response['xAxis']},
                        yaxis: {title: response['yAxis']},
                        title: response['graphTitle']
                      };
                      
                      Plotly.newPlot('plotgraph', data, layout);
                },
                error: function(jqXHR, textStatus, errorText){
                    console.log('Error while Plotting data - '+errorText);
                }
            })
        }
    });
});