from flask import Flask, render_template, request, jsonify, make_response, send_file, send_from_directory
from flask_cors import CORS
from PyPDF2 import PdfFileReader
import json
import os
import time
import pymongo
import string


app = Flask(__name__)

CORS(app)


dict_building_name = {"品园": 1, "知行": 2, "东风": 3}
dict_building_number = {"一楼": 1, "二楼": 2, "三楼": 3, "四楼": 4, "五楼": 5, "六楼": 6}

client = pymongo.MongoClient('localhost', 27017)
db = client['rucprintol'].get_collection('rucprintol')


@app.route('/')
def hello_world():
    return render_template('root.html')


@app.route('/order', methods=['POST'])
def place_new_order():
    json_data_dict = json.loads(request.get_data())

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
        'order_status': {
            'payment': False,
            'check': False,
            'print': False,
            'deliver': False
        },
        'trashed': False
    }
    db.insert_one(order)
    return jsonify({
        'order_id': order_id
    })


@app.route('/upload', methods=['POST'])
def file_upload():
    file = request.files['file']
    order_id = request.form['order_id']
    file.save('./files/' + order_id + '.pdf')
    num_pages = PdfFileReader(file).getNumPages()
    order_detail = db.find_one({'order_id': order_id}
                               )['order_detail']
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


@app.route('/pay', methods=['POST'])
def pay():
    order_id = json.loads(request.get_data())
    db.update_one(order_id, {"$set": {'order_status': {
        'payment': True,
        'check': False,
        'print': False,
        'deliver': False
    }}})
    return "ok"


@app.route('/querypayment', methods=['POST'])
def db_query_payment():
    query = json.loads(request.get_data())
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
            'order_payment': doc['order_status']['payment'],
            'order_check': doc['order_status']['check'],
            'order_print': doc['order_status']['print'],
            'order_deliver': doc['order_status']['deliver']
        })
    return jsonify({
        'data': arr_result
    })


@app.route('/queryprint', methods=['POST'])
def db_query_print():
    query = json.loads(request.get_data())
    db_result = db.find({
        'order_date': query['order_date'],
        'order_status': {
            'payment': True,
            'check': True,
            'print': False,
            'deliver': False
        },
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
            'order_print': doc['order_status']['print']
        })
    return jsonify({
        'data': arr_result
    })


@app.route('/querydeliver', methods=['POST'])
def db_query_deliver():
    query = json.loads(request.get_data())
    db_result = db.find({
        'order_date': query['order_date'],
        'order_status': {
            'payment': True,
            'check': True,
            'print': True,
            'deliver': False
        },
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
            'order_deliver': doc['order_status']['deliver']
        })
    return jsonify({
        'data': arr_result
    })


@app.route('/checkpayment', methods=['POST'])
def payment_check():
    db.find_one_and_update(json.loads(request.get_data()), {"$set": {'order_status': {
        'payment': True,
        'check': True,
        'print': False,
        'deliver': False
    }}})
    return "ok"


@app.route('/checkprint', methods=['POST'])
def print_check():
    db.find_one_and_update(json.loads(request.get_data()), {"$set": {'order_status': {
        'payment': True,
        'check': True,
        'print': True,
        'deliver': False
    }}})
    return "ok"


@app.route('/checkdeliver', methods=['POST'])
def deliver_check():
    db.find_one_and_update(json.loads(request.get_data()), {"$set": {'order_status': {
        'payment': True,
        'check': True,
        'print': True,
        'deliver': True
    }}})
    return "ok"


@app.route('/trash', methods=['POST'])
def trash_order():
    db.find_one_and_update(json.loads(request.get_data()), {
                           "$set": {'trashed': True}})
    return "ok"


@app.route('/getfile', methods=['POST'])
def get_file():
    order_id = json.loads(request.get_data())['order_id']
    filename = order_id + '.pdf'
    return send_from_directory('./files', filename, as_attachment=True)


app.run(debug=True, port=5000)
