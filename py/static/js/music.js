// define variables
window.AudioContext = window.AudioContext || window.webkitAudioContext;
var context = new AudioContext();
//var source = context.createBufferSource(); // creates a sound source
  var startTime=0
  function play(){
  $.ajax({
			type: 'POST',
			url: '/music',
			async: true,
			dataType:'json',
			success: function(data) 
			{
				var request = new XMLHttpRequest();
				request.open('GET', '/music', true);
				request.responseType = 'arraybuffer';

				request.onload = function() {
					/*var source = context.createBufferSource(); // creates a sound source
					//var temp = request.response;                    // tell the source which sound to play
					source.buffer = buffer;                    // tell the source which sound to play
					//var frameCount = data.sr * data.nc;
					//var myArrayBuffer = context.createBuffer(data.nc, frameCount, data.sr);
					source.connect(context.destination);       // connect the source to the context's destination (the speakers)
					source.start(0);*/
					var audioChunk = request.response; 
					var audioBuffer = context.createBuffer(data.nc, data.fc, data.sr);
					  audioBuffer.getChannelData(0).set(audioChunk);

					  var source = context.createBufferSource();
					  source.buffer = audioBuffer;
					  source.connect(context.destination);
					  source.start(0);
					  startTime += audioBuffer.duration;
					}
				request.send();
			}
		});	 
		
  

}
/*
var audioCtx = new (window.AudioContext || window.webkitAudioContext)();
var source;
var songLength;

var pre = document.querySelector('pre');
var myScript = document.querySelector('script');
var play = document.querySelector('.play');
var stop = document.querySelector('.stop');

var playbackControl = document.querySelector('.playback-rate-control');
var playbackValue = document.querySelector('.playback-rate-value');
playbackControl.setAttribute('disabled', 'disabled');

var loopstartControl = document.querySelector('.loopstart-control');
var loopstartValue = document.querySelector('.loopstart-value');
loopstartControl.setAttribute('disabled', 'disabled');

var loopendControl = document.querySelector('.loopend-control');
var loopendValue = document.querySelector('.loopend-value');
loopendControl.setAttribute('disabled', 'disabled');

// use XHR to load an audio track, and
// decodeAudioData to decode it and stick it in a buffer.
// Then we put the buffer into the source

function getData() {
  source = audioCtx.createBufferSource();
  request = new XMLHttpRequest();

  request.open('GET', '/ajax?option=12', true);

  request.responseType = 'arraybuffer';


  request.onload = function() {
    var audioData = request.response;

    audioCtx.decodeAudioData(audioData, function(buffer) {
        myBuffer = buffer;
        songLength = buffer.duration;
        source.buffer = myBuffer;
        source.playbackRate.value = playbackControl.value;
        source.connect(audioCtx.destination);
        source.loop = true;

        loopstartControl.setAttribute('max', Math.floor(songLength));
        loopendControl.setAttribute('max', Math.floor(songLength));
      },

      function(e){"Error with decoding audio data" + e.err});

  }

  request.send();
}

// wire up buttons to stop and play audio, and range slider control

play.onclick = function() {
  getData();
  source.start(0);
  play.setAttribute('disabled', 'disabled');
  playbackControl.removeAttribute('disabled');
  loopstartControl.removeAttribute('disabled');
  loopendControl.removeAttribute('disabled');
}

stop.onclick = function() {
  source.stop(0);
  play.removeAttribute('disabled');
  playbackControl.setAttribute('disabled', 'disabled');
  loopstartControl.setAttribute('disabled', 'disabled');
  loopendControl.setAttribute('disabled', 'disabled');
}

playbackControl.oninput = function() {
  source.playbackRate.value = playbackControl.value;
  playbackValue.innerHTML = playbackControl.value;
}

loopstartControl.oninput = function() {
  source.loopStart = loopstartControl.value;
  loopstartValue.innerHTML = loopstartControl.value;
}

loopendControl.oninput = function() {
  source.loopEnd = loopendControl.value;
  loopendValue.innerHTML = loopendControl.value;
}


// dump script to pre element

pre.innerHTML = myScript.innerHTML;*/