$(document).ready(function(){
    // ajax for POST - Download
    $(document).on('submit', '#download', function(e){
        e.preventDefault();
        $.ajax({
            type: 'GET',
            url: 'data/download',
            data: {
                tableName: $(this).find("#downloadButton").val()
            },
            success: function(response){
                if(response["status"] != null){
                    alert(response["status"])
                    return false
                }
            },
            error: function(jqXHR, textStatus, errorText){
                console.log('Error while downloading - '+errorText);
                alert("Not able to download the file, please contact the adminstrator")
                return false
            }
        });
    });
});


