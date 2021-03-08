var devicedata = {}
var socket = io();

socket.on('endscan', function() {
    console.log('Please Reload Browser!!');
	if ($('#myModal').is(':visible') == false){
		location.reload();
	}
});

function scanNetwork() {
	$("#scanbutton").prop("disabled", true);
	$.get( "scan", function( data ) {
		$("#scanbutton").prop("disabled", false);
		location.reload();
	});
}

$( document ).ready(function() {
	var myTH = document.getElementsByTagName("th")[1];
	sorttable.innerSortFunction.apply(myTH, []);
	$("#modal_icon").keyup(function(){
		var newval = $("#modal_icon").val();
		$("#iconpreview").text(newval);
	});

});

function editDevice(identifier) {
	devicedata = $(identifier).data();
	console.log(devicedata);
	$("#modal_created").text(devicedata['created']);
	$("#modal_vendor").text(devicedata['vendor']);
	$("#modal_hostname").text(devicedata['hostname']);
	$("#modal_ip").text(devicedata['ip']);
	$("#iconpreview").text(devicedata['icon']);
	$("#modal_mac").text(devicedata['mac']);

	$("#modal_icon").val(devicedata['icon']);
	$("#modal_brand").val(devicedata['brand']);
	$("#modal_devicetype").val(devicedata['devicetype']);
	$("#modal_is_recognized").prop("checked", devicedata['is_recognized']);
	$("#modal_model").val(devicedata['model']);
	$("#modal_name").val(devicedata['name']);
	$("#modal_notify_away").prop("checked", devicedata['notify_away']);
	$('#myModal').modal('show');
}

function saveDeviceChanges() {
	console.log('Form submitted!');

	newdevicedata = {}
	newdevicedata['mac'] = devicedata['mac'];
	newdevicedata['icon'] = $("#modal_icon").val();
	newdevicedata['brand'] = $("#modal_brand").val();
	newdevicedata['devicetype'] = $("#modal_devicetype").val();
	newdevicedata['is_recognized'] = $("#modal_is_recognized").prop("checked");
	newdevicedata['model'] = $("#modal_model").val();
	newdevicedata['name'] = $("#modal_name").val();
	newdevicedata['notify_away'] = $("#modal_notify_away").prop("checked");

	changed = true
	if (newdevicedata['icon'] == devicedata['icon'] &&
		newdevicedata['brand'] == devicedata['brand'] &&
		newdevicedata['devicetype'] == devicedata['devicetype'] &&
		newdevicedata['is_recognized'] == devicedata['is_recognized'] &&
		newdevicedata['model'] == devicedata['model'] &&
		newdevicedata['name'] == devicedata['name'] &&
		newdevicedata['notify_away'] == devicedata['notify_away']) {
		changed = false
	}

	if (changed === true){
		$.post( "update_device", newdevicedata, function( data ) {
			console.log(data);
			location.reload();
		});
	}

	$('#myModal').modal('hide');
	return true;
}
