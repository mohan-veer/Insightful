$(document).ready(function(){
    console.log("inside JS");

    //file name after uploading
    $('#customFile').on('change',function(){
        //get the file name
        var fileName = $(this).val().split("\\").pop();
        if(fileName.length != 0){
            console.log('the file name is = '+fileName);
            csvFileValidation(this);
            //remove the extension for fileNameChange
            fileName = fileName.split(".csv")[0];
            console.log('the file name is1 = '+fileName);
            //replace the "Choose a file" label
            $('#fileNameChange').val(fileName);
        }
    });
});

//validation for .csv file
function csvFileValidation(el) {
    var regex = new RegExp("(.*?)\.(csv)$");
    if (!(regex.test(el.value.toLowerCase()))) {
    el.value = '';
    alert('Please select correct file format');
    }
}
    