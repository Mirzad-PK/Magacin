<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pretraga i prikaz dokumenta alata</title>
    <!-- Biblioteka za čitanje Excel datoteka -->
    <script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script>
    <!-- Biblioteka za čitanje PDF datoteka -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js"></script>
    <style>
        * {
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        body {
            background-color: #f4f7f6;
            margin: 0;
            padding: 20px;
            color: #333;
        }

        .container {
            max-width: 1100px;
            margin: 0 auto;
            background: #ffffff;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        }

        h2 {
            margin-top: 0;
            color: #2c3e50;
            border-bottom: 2px solid #eceff1;
            padding-bottom: 10px;
        }

        .controls {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin-bottom: 20px;
            align-items: center;
        }

        .file-upload-btn {
            position: relative;
            display: inline-block;
            background-color: #3498db;
            color: white;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            transition: background 0.2s;
        }

        .file-upload-btn:hover {
            background-color: #2980b9;
        }

        .file-upload-btn input[type="file"] {
            display: none;
        }

        .search-box {
            flex: 1;
            min-width: 250px;
        }

        .search-box input {
            width: 100%;
            padding: 10px 15px;
            font-size: 16px;
            border: 2px solid #cbd5e1;
            border-radius: 6px;
            outline: none;
            transition: border-color 0.2s;
        }

        .search-box input:focus {
            border-color: #3498db;
        }

        .status-info {
            font-size: 14px;
            color: #64748b;
            margin-bottom: 10px;
        }

        .table-container {
            overflow-x: auto;
            max-height: 600px;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            text-align: left;
        }

        th {
            background-color: #2c3e50;
            color: white;
            padding: 12px 15px;
            position: sticky;
            top: 0;
            z-index: 10;
        }

        td {
            padding: 10px 15px;
            border-bottom: 1px solid #e2e8f0;
            font-size: 14px;
        }

        tr:nth-child(even) {
            background-color: #f8fafc;
        }

        tr:hover {
            background-color: #f1f5f9;
        }

        mark {
            background-color: #fef08a;
            color: #854d0e;
            padding: 2px 4px;
            border-radius: 3px;
            font-weight: bold;
        }

        .no-data {
            text-align: center;
            padding: 40px;
            color: #94a3b8;
            font-style: italic;
        }
    </style>
</head>
<body>

<div class="container">
    <h2>Pretraživanje i Prikaz Dokumenata Alata</h2>

    <div class="controls">
        <label class="file-upload-btn">
            Učitaj Excel, CSV ili PDF
            <input type="file" id="fileInput" accept=".xlsx, .xls, .csv, .pdf">
        </label>

        <div class="search-box">
            <input type="text" id="searchInput" placeholder="Unesite šifru alata, naziv ili ladicu (npr. tp 200-12.0-p)..." disabled>
        </div>
    </div>

    <div class="status-info" id="statusInfo">Molimo učitajte Excel, CSV ili PDF dokument.</div>

    <div class="table-container">
        <div id="tableOutput" class="no-data">Dokument još nije učitan.</div>
    </div>
</div>

<script>
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

    let rawData = [];
    let headers = [];

    const fileInput = document.getElementById('fileInput');
    const searchInput = document.getElementById('searchInput');
    const tableOutput = document.getElementById('tableOutput');
    const statusInfo = document.getElementById('statusInfo');

    fileInput.addEventListener('change', function (e) {
        const file = e.target.files[0];
        if (!file) return;

        statusInfo.textContent = `Učitavam dokument: "${file.name}"...`;

        if (file.name.toLowerCase().endsWith('.pdf')) {
            processPDF(file);
        } else {
            processExcelOrCSV(file);
        }
    });

    // Obrada Excel/CSV datoteka
    function processExcelOrCSV(file) {
        const reader = new FileReader();
        reader.onload = function (event) {
            const data = new Uint8Array(event.target.result);
            const workbook = XLSX.read(data, { type: 'array' });
            const firstSheetName = workbook.SheetNames[0];
            const worksheet = workbook.Sheets[firstSheetName];
            const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });

            if (jsonData.length > 0) {
                headers = jsonData[0];
                rawData = jsonData.slice(1).filter(row => row.length > 0);

                searchInput.disabled = false;
                searchInput.value = '';
                statusInfo.textContent = `Učitan dokument: "${file.name}" — Ukupno zapisa: ${rawData.length}`;
                renderTable(rawData);
            } else {
                tableOutput.innerHTML = '<div class="no-data">Dokument je prazan.</div>';
            }
        };
        reader.readAsArrayBuffer(file);
    }

    // Obrada PDF datoteka
    function processPDF(file) {
        const reader = new FileReader();
        reader.onload = function (event) {
            const typedarray = new Uint8Array(event.target.result);

            pdfjsLib.getDocument(typedarray).promise.then(async function (pdf) {
                headers = ["Stranica", "Sadržaj linije / Tekst"];
                rawData = [];

                for (let i = 1; i <= pdf.numPages; i++) {
                    const page = await pdf.getPage(i);
                    const textContent = await page.getTextContent();
                    
                    // Grupiranje teksta po linijama (na temelju Y-koordinate)
                    let linesMap = {};
                    textContent.items.forEach(item => {
                        let y = Math.round(item.transform[5]);
                        if (!linesMap[y]) linesMap[y] = [];
                        linesMap[y].push(item.str);
                    });

                    // Sortiranje linija od vrha prema dnu
                    let sortedY = Object.keys(linesMap).sort((a, b) => b - a);
                    sortedY.forEach(y => {
                        let lineText = linesMap[y].join(' ').trim();
                        if (lineText.length > 0) {
                            rawData.push([`Stranica ${i}`, lineText]);
                        }
                    });
                }

                if (rawData.length > 0) {
                    searchInput.disabled = false;
                    searchInput.value = '';
                    statusInfo.textContent = `Učitan PDF: "${file.name}" — Ukupno linija teksta: ${rawData.length}`;
                    renderTable(rawData);
                } else {
                    tableOutput.innerHTML = '<div class="no-data">Nije moguće izvući tekst iz ovog PDF-a.</div>';
                }
            }).catch(function (error) {
                statusInfo.textContent = "Greška pri otvaranju PDF dokumenta.";
                tableOutput.innerHTML = '<div class="no-data">Greška pri čitanju PDF-a.</div>';
            });
        };
        reader.readAsArrayBuffer(file);
    }

    searchInput.addEventListener('input', function () {
        const query = this.value.trim().toLowerCase();

        if (!query) {
            renderTable(rawData);
            statusInfo.textContent = `Ukupno zapisa: ${rawData.length}`;
            return;
        }

        const filteredData = rawData.filter(row => {
            return row.some(cell => {
                return cell !== null && cell !== undefined && cell.toString().toLowerCase().includes(query);
            });
        });

        statusInfo.textContent = `Pronađeno zapisa: ${filteredData.length} od ukupno ${rawData.length}`;
        renderTable(filteredData, query);
    });

    function renderTable(data, highlightQuery = '') {
        if (data.length === 0) {
            tableOutput.innerHTML = '<div class="no-data">Nema rezultata koji odgovaraju pretrazi.</div>';
            return;
        }

        let html = '<table><thead><tr>';
        headers.forEach(header => {
