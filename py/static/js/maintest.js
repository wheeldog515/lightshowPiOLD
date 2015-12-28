var selectedsong;
var settingsObj;
var currentAudio;
var selectedElement;
//var files;
var audioContext=false;
try{
window.AudioContext=window.AudioContext || window.webkitAudioContext;
audioContext = new window.AudioContext();
}catch(e){audioContext=false;}
var j=0;
var buffers=[];
var lastSample=0;
var playAudio=false;
var noConnection=false;

function refreshSchedule(){
	$.ajax({
			type: 'POST',
			url: '/ajax',
			data: 'option=15',
			dataType:'json',
			async: true,
			success: function(data)
			{
				var temp='';
				for (i in data){
					var theid=i;
					var theif=data[i][1];
					var thethen=data[i][2];
					temp+="<li class='scheduledevent' id='"+i+"'><a>IF "+theif+" THEN "+thethen+"</a></li>";
					$('#scheduleul').html(temp);
					try{$('#scheduleul').listview('refresh');}catch(e){}
				}
			}
		});	 
}

function getPlaylists(){
	$.ajax({
		type: 'POST',
		url: '/ajax',
		data: 'option=10',
		dataType:'json',
		async: true,
		success:function(data){
			refreshPlaylistUL(data);
		}
	});
}

function getSongs(){
	$.ajax({
		type: 'POST',
		url: '/ajax',
		data: 'option=8',
		dataType:'json',
		async: true,
		success: function(data)
		{
			var temp='';
			for(var i=0;i<data.songs.length;i++){
				temp+="<li data-theme='d'><a class='song' href='#' id='"+data.songs[i][1]+"'>"+data.songs[i][0]+"</a></li>";
			}
			$('#songsul').html(temp);
			try{$('#songsul').listview('refresh');}catch(e){}
		}
	});
}

function play(){

	var k=0;	
	while(buffers.length>0){
		var newbuffer=buffers.shift();
		newbuffer.connect(audioContext.destination);
		newbuffer.start(audioContext.currentTime+newbuffer.buffer.duration*k);
		k++;
	}
	play();
}


function equal (buf1, buf2)
{
	if (buf1.length != buf2.length) {return false;}
    for (var i = 0 ; i != buf1.length ; i++)
    {
        if (buf1[i] != buf2[i]) {return false;}
    }
    return true;
}

function run() {
  if(playAudio==true){
	var oReq = new XMLHttpRequest();
	oReq.open("POST", "ajax?option=14", true);
	oReq.responseType = "arraybuffer";
	oReq.onload = function (oEvent) {
	  
	  var samples = new Int16Array(oReq.response);

	  if(samples!=0 && (buffers.length==0 ||(buffers.length>0 && equal(lastSample,samples)==false))){
		  lastSample=samples;
		  var floatsLeft = new Float32Array(samples.length/2);
		  var floatsRight = new Float32Array(samples.length/2);

			for (var i = samples.length - 1; i >= 0; i--) {
			  
			  if(i%2 == 0)
				floatsLeft[i/2] = samples[i] < 0 ? samples[i] / 32768 : samples[i] / 32767;
			  else
				floatsRight[(i-1)/2] = samples[i] < 0 ? samples[i] / 32768 : samples[i] / 32767;
			};

			var audioBuffer = audioContext.createBuffer(2, samples.length/2, audioContext.sampleRate)

			var	bufferSource = audioContext.createBufferSource();

				audioBuffer.getChannelData(0).set(floatsLeft);
				audioBuffer.getChannelData(1).set(floatsRight);

				bufferSource.buffer = audioBuffer;
				
				buffers.push(bufferSource);
				run();
				if(j==0){
					if(buffers.length>40){
						play();
						j++;
					}
				}	
		}else{
			run();
		}
		
	};
	  oReq.send();
  }else{
	  buffers=[];
	  j=0;
  }
}

function refreshPlaylistUL(data){
	var temp1="<li data-theme='b' data-role='list-divider'>Playlists</li>";
	for(var i=0;i<data.playlists.length;i++){
		temp1+="<li data-theme='d'><a class='playlist' href='#' id='"+data.playlists[i][1]+"'>"+data.playlists[i][0]+"</a></li>"
	}
	$('#specificplaylistsul').html(temp1);
	$('#playlistsul').html(temp1);
	try{$('#playlistsul').html(temp1).listview('refresh');}catch(e){}
	try{$('#popupNewPlaylist').popup('close');}catch(e){}	
	try{$('#specificplaylistsul').listview('refresh');}catch(e){}
}

function refreshSongUL(data){
	var temp1="<li data-theme='b' data-role='list-divider'>Playlists</li>";
	for(var i=0;i<data.songs.length;i++){
		temp1+="<li data-theme='d'><a class='song' href='#' id='"+data.songs[i][1]+"'>"+data.songs[i][0]+"</a></li>"
	}
	$('#songsul').html(temp1).listview('refresh');
}


function getCurrentTrack(){
		$.ajax({
			type: 'POST',
			url: '/getvars',
			async: true,
			dataType:'json',
			success: function(data)
			{
				//data=JSON.parse(data);
				//console.log(data);
				if(noConnection==true){
					noConnection=false;
					refreshSchedule();
					getPlaylists();
					getSongs();
				}
				try{$('#popupError').popup('close');}catch(e){}
				if(data.currentsong!=''){
				$('.currentsong').html(data.currentsong);
				$('.currentpos').html(data.currentpos);
				$('.duration').html(data.duration);
				if(data.duration!=0)
				{
					$('.slider').attr('max',data.duration);
				}else
				{
					$('.slider').attr('max','100');
				}
				$('.slider').each(function(){
					try{$(this).val(data.currentpos).slider('refresh');}catch(e){}
				});
				}
				
				var temp='';
				for(var i=0;i<data.playlist.length;i++)
				{
					if(data.playlist[i]==data.playlistplaying)
					{
						temp+='<li data-song="'+data.playlist[i]+'" data-icon="audio"><a href="#">'+data.playlist[i]+'</a></li>';
						currentAudio=data.playlist[i]
					}
					else
					{
						temp+='<li data-song="'+data.playlist[i]+'">'+data.playlist[i]+'</li>';
					}
				}
				$(".playlistpanelul").html(temp);
				$(".playlistpanelul").each(function(){
					try{$(this).listview('refresh');;}catch(e){}
				});
			},
			error:function(a,e,b){
				if(e=='error'){
					$('#popupError').popup('open');
					noConnection=true;
				}
			},
			complete:function()
			{
				setTimeout(function(){getCurrentTrack()},1000);
			}
		});
	}

$(document).ready(function(){
		/*$.ajax({
			type: 'POST',
			url: '/ajax',
			async: true,
			data: 'option=5',
			success: function(data)
			{
				var ulVals='';
				settingsObj=JSON.parse(JSON.parse(data));
				for(temp in settingsObj){
					ulVals+='<li><a href="#'+temp+'" data-ajax="false">'+temp+'</a></li>';//console.log(temp)
					$('#tabs').append('<div id="'+temp+'" class="ui-body-d ui-content"></div>');
					for(temp2 in settingsObj[temp]){
						$('#'+temp).append('<div class="ui-field-contain"><label for="'+temp2+'">'+temp2+'</label><input name="'+temp2+'" id="'+temp2+'" value="'+settingsObj[temp][temp2]+'"></div>');
					}
					$('#'+temp).append('<button data-inline="true" data-theme="a" class="saveChanges">Save Changes</button><button data-theme="g" data-inline="true" class="applyChanges">Apply Changes</button>');
				}
				$('#tabsul').html(ulVals);
			}
		});*/
		
			$.ajax({
		type: 'POST',
		url: '/ajax',
		async: true,
		data: 'option=5',
		dataType:'json',
		success: function(data)
		{
			//get settings
			settingsObj=JSON.parse(JSON.stringify(data));
			console.log(settingsObj);
			//setup settings page
			var ulVals='';
			for(temp in settingsObj){
				ulVals+='<li><a href="#'+temp+'" data-ajax="false">'+temp+'</a></li>';//console.log(temp)
				$('#tabs').append('<div id="'+temp+'" class="ui-body-d ui-content"></div>');
				for(temp2 in settingsObj[temp]){
					if (settingsObj[temp][temp2] !== null && typeof settingsObj[temp][temp2] === 'object'){
					$('#'+temp).append('<div class="ui-field-contain"><label for="'+temp2+'">'+temp2+'</label><input name="'+temp2+'" id="'+temp2+'" value='+JSON.stringify(settingsObj[temp][temp2])+'></div>');
					}
					else{
					$('#'+temp).append('<div class="ui-field-contain"><label for="'+temp2+'">'+temp2+'</label><input name="'+temp2+'" id="'+temp2+'" value="'+settingsObj[temp][temp2]+'"></div>');
					}
				}
				$('#'+temp).append('<button data-inline="true" data-theme="g" class="saveChanges">Save Changes</button>');
                $('#'+temp).append('<button data-inline="true" data-theme="f" class="setDefault">Revert to Default</button>');
                $('#'+temp).append('<hidden name="section" id="section" value="'+temp+'">');
			}
			$('#tabsul').html(ulVals);
				
			//setup lighting controls
			var lights = settingsObj.hardware.gpio_pins.split(",")
			var lightstr="<li data-theme='b' data-role='list-divider'>Current Light States</li>";
			for (var i=0;i<lights.length;i++){
				lightstr += "<li data-theme='d'><a data-index='"+i+"' class='light' id='light"+i+"'>Light "+ i +"</a></li>";
			}
				$('#lightsUl').html(lightstr);
		}
		});
		
		$('#lightsUl').on('click',".light",function() {
			var port=$(this).data('index');
			if($(this).hasClass('ui-btn-d')){
				$(this).removeClass("ui-btn-d").addClass("ui-btn-e");
				$.ajax({
					type: "POST", 
					url: '/ajax', 
					data: {option:'lightOn', port:port}, 
					async: true
				});
			}
			else{
				$(this).removeClass("ui-btn-e").addClass("ui-btn-d");
				$.ajax({
					type: "POST", 
					url: '/ajax', 
					data: {option:'lightOff', port:port},
					async: true
				});
			}
		});
				
 $('.playAudioBtn').click(function(){
	if(audioContext!=false){
		if(playAudio==false){
			playAudio=true;
			$('.playAudioBtn').html('Stop Audio');
			run();
			}
			else{
				playAudio=false;
				$('.playAudioBtn').html('Play Audio');
			}
	}else{
		alert('Live Audio is not supported in your browser');
	}
 });
 
 $('#uploadfile').on('submit', function(e)
	{
		e.stopPropagation(); // Stop stuff happening
		e.preventDefault(); // Totally stop stuff happening
	$('progress').css({visibility: 'visible'});
	
    var formData = new FormData($(this)[0]);
    $.ajax({
        url: '/upload',  //Server script to process data
        type: 'POST',
		data: formData,
		dataType:'json',
        xhr: function() {  // Custom XMLHttpRequest
            var myXhr = $.ajaxSettings.xhr();
            if(myXhr.upload){ // Check if upload property exists
                myXhr.upload.addEventListener('progress',progressHandlingFunction, false); // For handling the progress of the upload
            }
            return myXhr;
        },
        success: function(data){
			$('#uploadfile')[0].reset();
			$('progress').css({visibility: 'hidden'});
			$('progress').attr({value:0,max:100});
			refreshSongUL(data);
		},
        error: function(jqXHR, textStatus, errorThrown)
		{
			alert('ERRORS: ' + textStatus);
		},
        cache: false,
        contentType: false,
        processData: false
    });
});

function progressHandlingFunction(e){
    if(e.lengthComputable){
        $('progress').attr({value:e.loaded,max:e.total});
    }
}
	$('#tabs').on('click','.setDefault',function(){
		var a=confirm('Are you sure you want to reset the Config');
		if(a){
			$.ajax({
				type: 'POST',
				url: '/ajax',
				async: true,
				data: 'option=11'
			});
		}
	});
		
	$('#tabs').on('click','.saveChanges',function(){
		var config = {};
		for(obj in settingsObj){
		config[obj]={};
		$('#'+obj+' input').serializeArray().map(function(item) {
			config[obj][item.name] = item.value;
			});
		}
		$.ajax({
			type: 'POST',
			url: '/ajax',
			async: true,
			data: 'option=6&object='+JSON.stringify(config)
			});
	});
	
	$('#songsul').on('click','.song',function(){
		selectedsong=this.id;
		$('#popupTitle').html($(this).html());
		$("#popupSong").popup('open');
	});
	
	$('#playNow').click(function()
	{
		$("#popupSong").popup('close');
		$.ajax({
			type: 'POST',
			url: '/ajax',
			data: 'option=1&song='+selectedsong,
			async: true
		});
	});
	
	$('#playlistsul').on('click','.playlist',function(){
		selectedsong=this.id;
		$('#popupTitlelist').html($(this).html());
		$("#popupPlaylist").popup('open');
	});
	
	$('#playNowlist').click(function()
	{
		$("#popupPlaylist").popup('close');
		$.ajax({
			type: 'POST',
			url: '/ajax',
			data: 'option=0&playlist='+selectedsong,
			async: true
		});
	});
	
	$('#Audioin').click(function(){
		console.log('option 16');
		$.ajax({
			type: 'POST',
			url: '/ajax',
			data: 'option=16',
			async: true
		});	
	});
	
	$('#dialogContent').on('click','#removeItem',function(){
		$("#popupDialog").popup('close');
		$.ajax({
			type: 'POST',
			url: '/scheduler',
			data: 'option=2&id='+selectedElement.attr('id'),
			async: true,
			success: function(data)
			{
				//selectedElement.remove();
				refreshSchedule();
				$('#scheduleul').listview('refresh');
			}
		});
	});
	
	$('#deletelist').click(function()
	{
		var a=confirm('Are you sure you want to delete this playlist');
		if(a){
			$("#popupPlaylist").popup('close');
			$.ajax({
				type: 'POST',
				url: '/ajax',
				data: 'option=10&playlist='+selectedsong,
				dataType:'json',
				async: true,
				success:function(data){
					refreshPlaylistUL(data);
				}
			});			
		}
	});

	$('#addToQueue').click(function()
	{
		$("#popupSong").popup('close');
		$.ajax({
			type: 'POST',
			url: '/ajax.php',
			data: 'option=5&song='+selectedsong,
			async: true
		});
	});
	
	$('#lightsOn').click(function()
	{
		$.ajax({
			type: 'POST',
			url: '/ajax',
			data: 'option=3',
			async: true/*,
			success: function(data)
			{

			}*/
		});
	});
	
	$('#tabs').on('click','.saveChanges',function(){
		var config = {};
		for(obj in settingsObj){
		config[obj]={};
		$('#'+obj+' input').serializeArray().map(function(item) {
			config[obj][item.name] = item.value;
			});
		}
		$.ajax({
			type: 'POST',
			url: '/ajax',
			async: true,
			data: 'option=6='+JSON.stringify(config)
			});
	});
	
	$('#lightsOff').click(function()
	{
		$.ajax({
			type: 'POST',
			url: '/ajax',
			data: 'option=4',
			async: true/*,
			success: function(data)
			{

			}*/
		});
	});	
	
	$('#restartPi').click(function(){
		$('#popupRestart').popup('open');
	});
	
	$('#shutdownPi').click(function(){
		$('#popupShutdown').popup('open');
	});
	
	$('#restartPiConfirm').click(function(){
		$('#popupRestart').popup('close');
		$.ajax({
			type: 'POST',
			url: '/ajax',
			data: 'option=13',
			async: true
		});
	});
	
	$('#shutdownPiConfirm').click(function(){
		$('#popupShutdown').popup('close');
		$.ajax({
			type: 'POST',
			url: '/ajax',
			data: 'option=12',
			async: true
		});
	});
	
	$('#playallmusic').click(function()
	{
		$.ajax({
			type: 'POST',
			url: '/ajax',
			data: 'option=7',
			async: true
		});
	});
	
	$("#playlistsongs").on('click','.songsforplaylist',function()
	{
		if($(this).hasClass('ui-btn-d')){
			$(this).removeClass("ui-btn-d").addClass("ui-btn-e");
		}
		else{
			$(this).removeClass("ui-btn-e").addClass("ui-btn-d");
		}
	});
	
	$('#newplaylistsubmit').click(function(){
		var name=$("#newplaylistname").val();
		if(name==''){
			alert('Please Enter a name');
			return false;
		}
		var temp='';
		$('.songsforplaylist.ui-btn-e').each(function(){
			temp+=$(this).html().replace(/\.[^/.]+$/, "")+"\t"+$(this).data('filename')+"\r\n";
		});
		$.ajax({
			type: 'POST',
			url: '/ajax',
			data: 'option=9&val='+temp+'&name='+name,
			async: true,
			dataType:'json',
			success: function(data)
			{
				refreshPlaylistUL(data);
			}
		});		
	});
	
	$('#newplaylist').click(function(){
		$.ajax({
			type: 'POST',
			url: '/ajax',
			data: 'option=8',
			dataType:'json',
			async: true,
			success: function(data)
			{
				var temp='';
				for(var i=0;i<data.songs.length;i++){
					temp+="<li data-theme='d'><a class='songsforplaylist' href='#' data-filename=\""+data.songs[i][1]+"\">"+data.songs[i][0]+"</a></li>";
				}
				$('#playlistsongs').html(temp);
				try{$('#playlistsongs').listview('refresh');}catch(e){$('#playlistsongs').listview();}
				$('#popupNewPlaylist').popup('open');
			}
		});
	});
	
	$("#if").change(function(){
		if ($(this).val()=='Specific Time'){
			$('#popuptime').popup('open');
		}
	});
	
	$("#then").change(function(){
		if ($(this).val()=='playlist'){
			$('#popupspecifiplaylist').popup('open');
		}
	});
	
	$("#specificplaylistsul").on('click','.playlist',function(){
		$('#specificplaylist').val(this.id);
		$('#specificplaylist').data('name',$(this).html());
			$('#popupspecifiplaylist').popup('close');
	});
	
	$('#timeconfirm').click(function()
	{
		if($('#popuptimefield').val()!=''){
			$('#specifictime').val($('#popuptimefield').val());
			$('#popuptime').popup('close');
		}
		else{alert('Please enter a valid time');}
	});
	
	$('#addschedule').click(function(){
		var temp;
		var type;
		var params;
		
		if($('#theif').val()=='Please Specify'){
			alert('Please specify a if event');
			return false;
		}	
		else if($('#thethen').val()=='Please Specify'){
			alert('Please specify a then event');
			return false;
		}
	
		if($('#specifictime').val()!=''){
			//temp='IF '+ $("#specifictime").val() + ' THEN '+ $("#then").val()+' '+$('#specificplaylist').data('name');
			type='time';
			params='&theif='+$("#specifictime").val() + '&thethen='+ $("#then").val()+'&arg='+$('#specificplaylist').val();
		}
		else{
			//temp='IF '+ $("#if").val() + ' THEN '+ $("#then").val()+' '+$('#specificplaylist').data('name');
			type='event';
			params='&theif='+$("#if").val() + '&thethen='+ $("#then").val()+'&arg='+$('#specificplaylist').val();
		}
		
		$.ajax({
			type: 'POST',
			url: '/scheduler',
			data: 'option=0&type='+type+params,
			async: true,
			success: function(data)
			{
				//$('#scheduleul').append("<li class='scheduledevent' id='"+data+"'><a>"+temp+"</a></li>").listview('refresh');
				$('#specifictime').val('');
				$('#specificplaylist').val('').data('name','');
				$('#theif').val('Please Specify').selectmenu('refresh');
				$('#thethen').val('Please Specify').selectmenu('refresh');
				refreshSchedule();
			}
		});	 
	});
	
	
	$('#scheduler').on('pageshow',function(){
		$('#scheduleul').listview('refresh');
	});
	
	$('#songs').on('pageshow',function(){
		$('#songsul').listview('refresh');
	});
	
	$('#playlists').on('pageshow',function(){
		$('#playlistsul').listview('refresh');
	});
	
	$('#scheduleul').on('click','.scheduledevent',function()
	{
		selectedElement=$(this);
		$('#dialogContent').html('<h3 class="ui-title">Are you sure you want to remove this Scheduled Item?</h3>'+
					'<h4>This will completely remove the item.</h4><h4>THIS CANNOT BE UNDONE!</h4>'+
					'<a href="#" class="ui-btn ui-corner-all ui-shadow ui-btn-inline ui-btn-b"id="removecancel" data-rel="back">Cancel</a>'+
					'<a href="#" class="ui-btn ui-corner-all ui-shadow ui-btn-inline ui-btn-b"id="removeItem">Remove Item</a>');
		$('#popupDialog').popup('open');
		/*var a=confirm('are you sure you want to delete this event');
		if (a)
		{
			$.ajax({
			type: 'POST',
			url: '/scheduler',
			data: 'option=2&id='+element.attr('id'),
			async: true,
			success: function(data)
			{
				element.remove();
				$('#scheduleul').listview('refresh');
			}
		});	 
		}*/
	});
	refreshSchedule();
	getPlaylists();
	getSongs();
});