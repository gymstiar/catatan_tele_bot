function doPost(e) {
    var sheet = SpreadsheetApp.openById("isi dengan id Spreadsheet").getSheetByName("Sheet1");
    var data = JSON.parse(e.postData.contents);
    
    var waktu = new Date();
    var tanggal = Utilities.formatDate(waktu, "GMT+7", "dd-MM-yyyy"); // Format tanggal
    var nominal = data.nominal;
    var kategori = data.kategori;
    var keterangan = data.keterangan;
    
    sheet.appendRow([waktu, nominal, kategori, keterangan]);

    // Format response
    var responseMessage = `Catatan dengan deskripsi : \n\n` +
                          `📅 Tanggal : ${tanggal}\n` +
                          `🏷 Kategori : ${kategori}\n` +
                          `💰 Nominal : Rp. ${Number(nominal).toLocaleString("id-ID")}\n` +
                          `📝 Keterangan : ${keterangan}\n\n` +
                          `Berhasil disimpan ✅  \n\n` +
                          
                          'WARNING: Jangan boros boros yaahh ☺️';

    return ContentService.createTextOutput(responseMessage);
}

function doGet(e) {
  var action = e.parameter.action;
  if (action === "getData") {
    return getData();
  }
}

function getData() {
  var sheet = SpreadsheetApp.openById("id_spreadsheet").getSheetByName("Sheet1");
  var data = sheet.getDataRange().getValues();
  
  var result = [];
  for (var i = 1; i < data.length; i++) {  // Mulai dari baris kedua (tanpa header)
    var tanggal = Utilities.formatDate(new Date(data[i][0]), "GMT+7", "dd-MM-yyyy"); // Format tanggal
    result.push({
      tanggal: tanggal, 
      nominal: data[i][1],  
      kategori: data[i][2],  
      keterangan: data[i][3]  
    });
  }
  
  return ContentService.createTextOutput(JSON.stringify(result))
                       .setMimeType(ContentService.MimeType.JSON);
}
