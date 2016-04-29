var dive = require('dive');
var fs = require('graceful-fs');
var sleep = {};
var obj = [];

dive('./json', function(err, file) {
	if (err) throw err;
	console.log(file);

	fs.readFile(file, 'utf8', function (err, data) {
		if (err) throw err;
		var content = JSON.parse(data);
		obj.push(content.content);
		if(obj.length === 669) {
			sleep.obj = obj;
			sleep = JSON.stringify(sleep);
			fs.writeFile("allSleep.json", sleep, function(err) {
		    	if(err) {
		       	 return console.log(err);
		    	}
    
    			console.log("The file was saved!");
			}); 
		}
	});

}, function() {
	console.log('dive complete');
});



