from flask import Flask, render_template, request, jsonify, make_response, send_file, send_from_directory
from flask_cors import CORS
from PyPDF2 import PdfFileReader
import json
import os
import time
import pymongo
import string
import math

app = Flask(__name__)

CORS(app)


dict_building_name = {"品园": 1, "知行": 2, "东风": 3}
dict_building_number = {"一楼": 1, "二楼": 2, "三楼": 3, "四楼": 4, "五楼": 5, "六楼": 6}

client = pymongo.MongoClient('localhost', 27017)
db = client['rucprintol'].get_collection('rucprintol')


@app.route('/api')
def hello_world():
    return render_template('root.html')


@app.route('/api/order', methods=['POST'])
def place_new_order():
    json_data_dict = json.loads(request.get_data().decode())

    id_prefix = str(dict_building_name[json_data_dict['customer_building_name']
                                       ]) + str(dict_building_number[json_data_dict['customer_building_number']])
    id_suffix = db.count_documents({}) + 1
    order_id = id_prefix + "%05d" % id_suffix
    order = {
        'order_id': order_id,
        'order_date': time.strftime("%Y%m%d", time.localtime()),
        'order_time': time.strftime("%H:%M:%S", time.localtime()),
        'order_detail': json_data_dict,
        'document_numpages': 0,
        'document_total_price': 0,
        'order_status_payment': False,
        'order_status_check': False,
        'order_status_print': False,
        'order_status_deliver': False,
        'trashed': False
    }
    db.insert_one(order)
    return jsonify({
        'order_id': order_id
    })


@app.route('/api/upload', methods=['POST'])
def file_upload():
    file = request.files['file']
    order_id = request.form['order_id']
    order_detail = db.find_one({'order_id': order_id}
                               )['order_detail']
    file.save('/var/www/html/static/' + order_id + '.pdf')
    num_pages = PdfFileReader(file).getNumPages()
    if 'pptOption' in order_detail
        if order_detail['pptOption'] == '四合一':
            num_pages = math.ceil(float(num_pages) / 4)
        if order_detail['pptOption'] == '六合一':
            num_pages = math.ceil(float(num_pages) / 6)
    total_price = (float(order_detail['unit_price']) * num_pages +
                   float(order_detail['binding_price']))*float(order_detail['total_copy_count'])
    db.update_one({'order_id': order_id}, {
        "$set": {
            'document_numpages': num_pages,
            'document_total_price': total_price,
        }
    })
    return jsonify({
        'num_pages': num_pages,
        'total_price': "%.2f" % total_price
    })


@app.route('/api/pay', methods=['POST'])
def pay():
    order_id = json.loads(request.get_data().decode())
    db.update_one(order_id, {"$set": {'order_status_payment': True}})
    return "ok"


@app.route('/api/querypayment', methods=['POST'])
def db_query_payment():
    query = json.loads(request.get_data().decode())
    db_result = db.find({
        'order_date': query['order_date'],
        'trashed': False
    })
    arr_result = []
    for doc in db_result:
        arr_result.append({
            'order_id': doc['order_id'],
            'customer_name': doc['order_detail']['customer_name'],
            'customer_phone': doc['order_detail']['customer_phone'],
            'document_total_price': doc['document_total_price'],
            'document_numpages': doc['document_numpages'],
            'paper_binding': doc['order_detail']['paper_binding'],
            'customer_room_number': doc['order_detail']['customer_room_number'],
            'order_payment': doc['order_status_payment'],
            'order_check': doc['order_status_check'],
            'order_print': doc['order_status_print'],
            'order_deliver': doc['order_status_deliver'],
            'shareOption': doc['order_detail']['shareOption'],
            'pptOption': doc['order_detail']['pptOption']
        })
    return jsonify({
        'data': arr_result
    })


@app.route('/api/queryprint', methods=['POST'])
def db_query_print():
    query = json.loads(request.get_data().decode())
    db_result = db.find({
        'order_date': query['order_date'],
        'order_status_payment': True,
        'order_status_check': True,
        'trashed': False
    })
    arr_result = []
    for doc in db_result:
        arr_result.append({
            'order_id': doc['order_id'],
            'customer_name': doc['order_detail']['customer_name'],
            'customer_phone': doc['order_detail']['customer_phone'],
            'paper_type': doc['order_detail']['paper_type'],
            'paper_size': doc['order_detail']['paper_size'],
            'paper_color': doc['order_detail']['paper_color'],
            'paper_sig_or_dbl': doc['order_detail']['paper_sig_or_dbl'],
            'paper_binding': doc['order_detail']['paper_binding'],
            'total_copy_count': doc['order_detail']['total_copy_count'],
            'order_print': doc['order_status_print'],
            'document_numpages': doc['document_numpages'],
            'pptOption': doc['order_detail']['pptOption']
        })
    return jsonify({
        'data': arr_result
    })


@app.route('/api/querydeliver', methods=['POST'])
def db_query_deliver():
    query = json.loads(request.get_data().decode())
    db_result = db.find({
        'order_date': query['order_date'],
        'order_status_payment': True,
        'order_status_check': True,
        'order_status_print': True,
        'order_status_deliver': False,
        'trashed': False
    })
    arr_result = []
    for doc in db_result:
        arr_result.append({
            'order_id': doc['order_id'],
            'customer_name': doc['order_detail']['customer_name'],
            'customer_phone': doc['order_detail']['customer_phone'],
            'customer_building_name': doc['order_detail']['customer_building_name'],
            'customer_building_number': doc['order_detail']['customer_building_number'],
            'customer_room_number': doc['order_detail']['customer_room_number'],
            'total_copy_count': doc['order_detail']['total_copy_count'],
            'order_deliver': doc['order_status_deliver']
        })
    return jsonify({
        'data': arr_result
    })


@app.route('/api/checkpayment', methods=['POST'])
def payment_check():
    db.find_one_and_update(json.loads(request.get_data().decode()), {
                           "$set": {'order_status_check': True, 'order_status_payment': True}})
    return "ok"


@app.route('/api/checkprint', methods=['POST'])
def print_check():
    db.find_one_and_update(json.loads(request.get_data().decode()), {
                           "$set": {'order_status_print': True}})
    return "ok"


@app.route('/api/checkdeliver', methods=['POST'])
def deliver_check():
    db.find_one_and_update(json.loads(request.get_data().decode()), {
                           "$set": {'order_status_deliver': True}})
    return "ok"


@app.route('/api/trash', methods=['POST'])
def trash_order():
    db.find_one_and_update(json.loads(request.get_data().decode()), {
                           "$set": {'trashed': True}})
    return "ok"


@app.route('/api/getfile', methods=['POST'])
def get_file():
    order_id = json.loads(request.get_data().decode())['order_id']
    filename = order_id + '.pdf'
    return send_from_directory('/var/www/html', filename, as_attachment=True)
