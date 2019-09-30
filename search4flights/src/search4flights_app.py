from flask import Flask, render_template, request, escape
from UseDatabase import UseDatabase
import pickle
import pprint
import requests
from bs4 import BeautifulSoup
import html5lib
import threading
from datetime import datetime


app = Flask(__name__)


with open('db_config.pkl', 'rb') as db_config:
   app.config['dbconfig'] = pickle.load(db_config)

# Default setting for the flight searching results
# app.config['flightsconfig'] = { 'srcAirport': '%5BWAW%5D+%28%2BWMI%29 ',
#                                'dstAirport': '%5BXXX%5D',
#                                'anywhere': 'true',
#                                'depdate': '2019-09-01',
#                                'arrdate': '2019-08-31',
#                                'minDaysStay': '5',
#                                'maxDaysStay': '8',
#                                'samedep': 'true',
#                                'samearr': 'true',
#                                'minHourStay': '0%3A45',
#                                'maxHourStay': '23%3A20',
#                                'minHourOutbound': '0%3A00',
#                                'maxHourOutbound': '24%3A00',
#                                'minHourInbound': '0%3A00',
#                                'maxHourInbound': '24%3A00',
#                                'autoprice': 'true',
#                                'adults': '1',
#                                'children': '0',
#                                'infants': '0',
#                                'maxChng': '0',
#                                'currency': 'PLN',
# }
#
#
# with open('flights_config.pkl', 'wb') as flights_config:
#     pickle.dump(app.config['flightsconfig'], flights_config)

# Default settings for search engine configuration
# app.config['searchengineconfig'] = { 'search_delay': 300
#                             }
# with open('search_engine_config.pkl', 'wb') as search_engine_config:
#     pickle.dump(app.config['searchengineconfig'], search_engine_config)

with open('search_engine_config.pkl', 'rb') as search_engine_config:
    app.config['searchengineconfig'] = pickle.load(search_engine_config)

with open('flights_config.pkl', 'rb') as flights_config:
    app.config['flightsconfig'] = pickle.load(flights_config)




def get_http_request():
    url = 'http://www.azair.eu/azfin.php?searchtype=flexi&isOneway=return'
    url += '&srcAirport=' + app.config['flightsconfig']['srcAirport']
    url += '&dstAirport=' + app.config['flightsconfig']['dstAirport']
    url += '&anywhere=true'
    url += '&depdate=' + app.config['flightsconfig']['depdate']
    url += '&arrdate=' + app.config['flightsconfig']['arrdate']
    url += '&minDaysStay=' + app.config['flightsconfig']['minDaysStay']
    url += '&maxDaysStay=' + app.config['flightsconfig']['maxDaysStay']
    url += '&samedep=true'
    url += '&samearr=true'
    url += '&minHourStay=0%3A45'
    url += '&maxHourStay=23%3A20'
    url += '&minHourOutbound=0%3A00'
    url += '&maxHourOutbound=24%3A00'
    url += '&minHourInbound=0%3A00'
    url += '&maxHourInbound=24%3A00'
    url += '&autoprice=true'
    url += '&adults=' + app.config['flightsconfig']['adults']
    url += '&children=' + app.config['flightsconfig']['children']
    url += '&infants=' + app.config['flightsconfig']['infants']
    url += '&maxChng=' + app.config['flightsconfig']['maxChng']
    url += '&currency=' + app.config['flightsconfig']['currency']
    url += '&indexSubmit=Szukaj'
    http_response = requests.get(url)
    soup = BeautifulSoup(http_response.text, 'html5lib')
    flights_results = soup.find_all('div', attrs={'class':'result'})



    for flight_result in flights_results:

        # Loading DEPARTURE PLACE (airport) and DEPARTURE HOUR (when departing)
        res = flight_result.find_all('span', attrs={'class': 'from'})
        text = res[0].text.split(' ')
        text[2] = text[2].replace(text[1], '')
        dep_place = text[1] + ' ' + text[2]
        dep_hours = text[0]

        # Loading RETURN HOUR (when returning)
        text = res[2].text.split(' ')
        return_hours = text[0]

        # Loading ARRIVAL PLACE (airport) and DEPARTURE HOUR (when arriving in destination)
        res = flight_result.find_all('span', attrs={'class': 'to'})
        text = res[0].text.split(' ')
        text[2] = text[2].replace(text[1], '')
        arr_place = text[1] + ' ' + text[2]
        dep_hours += '|' + text[0]

        # Loading RETURN HOUR (when arriving back home)
        text = res[2].text.split(' ')
        return_hours += '|' + text[0]

        # Loading the LENGTH OF YOUR STAY
        res = flight_result.find_all('span', attrs={'class': 'lengthOfStay'})
        text = res[0].text.split(':')
        len_stay = text[1]

        # Creating a FLIGHT ROUTE NAME based on dep and arr places end length of stay
        flight_route_name = dep_place + '-' + arr_place + ':' + len_stay

        # Checking if table of this route exists in DB
        # If not the new one is created

        try:
            with UseDatabase(app.config['dbconfig']) as cursor:
                _SQL = 'SHOW TABLES'
                cursor.execute(_SQL)
                contents = cursor.fetchall()
                flights_routes = [route[0] for route in contents]
                if (flight_route_name.lower() not in flights_routes):

                    _SQL = 'create table `' + flight_route_name + """` (
                    id int auto_increment primary key,
                    ts timestamp default current_timestamp ON UPDATE CURRENT_TIMESTAMP,
                    Departure_place varchar(128) not null,
                    Departure_flight_numb varchar(32) not null,
                    Departure_date varchar(64) not null,
                    Departure_hours varchar(32) not null,
                    Departure_changes varchar(32) not null,
                    Departure_flight_time varchar(32) not null,
                    Destination_place varchar(128) not null,
                    Return_flight_numb varchar(32) not null,
                    Return_date varchar(64) not null,
                    Return_hours varchar(32) not null,
                    Return_changes varchar(32) not null,
                    Return_flight_time varchar(32) not null, 
                    Price int not null )"""
                    cursor.execute(_SQL)


        except Exception as err:
            print('Something went wrong...: ', str(err))


        # Loading DEPARTURE and RETURN FLIGHT NUMBERS
        res = flight_result.find_all('a', attrs={'title': 'flightradar24'})
        dep_flight_numb = res[0].text
        ret_flight_numb = res[1].text

        # Loading PRICE OF THE FLIGHT
        res = flight_result.find_all('span', attrs={'class': 'tp'})
        text = res[0].text.split(' ')
        price = int(text[0])

        # Loading DEPARTURE DATE
        res = flight_result.find_all('span', attrs={'class': 'date'})
        dep_date = res[0].text.replace('/', '-')

        # Loading RETURN DATE
        return_date = res[1].text.replace('/', '-')

        # Checking the database table whether this particular flight already exists in it
        # If it exists program checks the price and updates record in database if it changed
        # If not it stays the same, but timestamp changes for present moment
        # If there is no record of those flights numbers a new record is inserted to the database
        try:
            with UseDatabase(app.config['dbconfig']) as cursor:
                _SQL = 'select Departure_flight_numb, Return_flight_numb, Price, id, Departure_date, Departure_hours, Return_date, Return_hours from `' + flight_route_name.lower() + '`'
                cursor.execute(_SQL)
                contents = cursor.fetchall()
                # Results of the SELECT query stored in lists
                dep_numbs = [numb[0] for numb in contents]
                ret_numbs = [numb[1] for numb in contents]
                prices = [numb[2] for numb in contents]
                ids = [numb[3] for numb in contents]
                dep_dates = [numb[4] for numb in contents]
                depart_hours = [numb[5] for numb in contents]
                ret_dates = [numb[6] for numb in contents]
                ret_hours = [numb[7] for numb in contents]

                flight_in_db = False
                for i in range (0, len(dep_numbs)):
                    if(dep_flight_numb==dep_numbs[i] and ret_flight_numb==ret_numbs[i] and dep_date==dep_dates[i] and dep_hours==depart_hours[i] and return_date==ret_dates[i] and return_hours==ret_hours[i]):
                        if(price != prices[i]):
                            _SQL = 'UPDATE `' + flight_route_name +'` SET Price=\'' + str(price) +'\' WHERE id=' + str(ids[i])
                            cursor.execute(_SQL)
                        else:
                            _SQL = 'UPDATE `' + flight_route_name + '` SET Price=\'' + str(prices[i]+1) + '\' WHERE id=' + str(ids[i])
                            cursor.execute(_SQL)
                            _SQL = 'UPDATE `' + flight_route_name + '` SET Price=\'' + str(prices[i]-1) + '\' WHERE id=' + str(ids[i])
                            cursor.execute(_SQL)
                        flight_in_db = True

                # Checks if the flight of that number was not found and inserts a new record
                if (flight_in_db == False):
                    # Loading TRAVEL TIME and NUMBE OF CHANGES for DEPARTURE FLIGHT
                    res = flight_result.find_all('span', attrs={'class': 'durcha'})
                    text = res[0].text.split('/')
                    travel_time_dep = text[0]
                    changes_dep = text[1]

                    # Loading TRAVEL TIME and NUMBE OF CHANGES for RETURN FLIGHT
                    text = res[1].text.split('/')
                    travel_time_return = text[0]
                    changes_return = text[1]


                    _SQL = 'INSERT INTO `' + flight_route_name + """` 
                    (`Departure_place`, `Departure_flight_numb`, 
                    `Departure_date`, `Departure_hours`, `Departure_changes`, 
                    `Departure_flight_time`, `Destination_place`, `Return_flight_numb`, 
                    `Return_date`, `Return_hours`, `Return_changes`, `Return_flight_time`, `Price`) VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) """
                    cursor.execute(_SQL, (dep_place, dep_flight_numb, dep_date, dep_hours, changes_dep, travel_time_dep,
                                          arr_place, ret_flight_numb, return_date, return_hours, changes_return, travel_time_return, price))


        except Exception as err:
            print('Something went wrong...: ', str(err))

    try:
        print('DB updated: ' + str(datetime.now()))
        threading.Timer(float(app.config['searchengineconfig']['search_delay']), get_http_request).start()
    except Exception as err:
        print('Something went wrong...: ', str(err))



get_http_request()

@app.route('/')
@app.route('/home')
def home_page() -> 'html':
    return render_template('entry.html',
                           the_title='Flight Search Engine')


@app.route('/flights_list')
def flights_list_page() -> 'html':

    try:
        with UseDatabase(app.config['dbconfig']) as cursor:
            _SQL = 'SHOW TABLES'
            cursor.execute(_SQL)
            contents = cursor.fetchall()
            flights_routes = [route[0] for route in contents]

    except Exception as err:
        print('Something went wrong...: ', str(err))

    return render_template('flights_list.html',
                           the_title='Flight Search Engine',
                           flights_results = flights_routes)

@app.route('/show_results/<string:flight_route>')
def show_flight_results(flight_route: str) -> 'html':
    try:
        with UseDatabase(app.config['dbconfig']) as cursor:
            _SQL = """SELECT `Departure_place`, `Departure_flight_numb`, `Departure_date`, 
                      `Departure_hours`, `Departure_changes`, `Departure_flight_time`, 
                      `Destination_place`, `Return_flight_numb`, `Return_date`, `Return_hours`, 
                      `Return_changes`, `Return_flight_time`, `Price`, `ts` FROM `""" + flight_route + '` ORDER BY Price'

            cursor.execute(_SQL)
            contents = cursor.fetchall()
        titles = ('Departure_place', 'Departure_flight_numb', 'Departure_date',
                      'Departure_hours', 'Departure_changes', 'Departure_flight_time',
                      'Destination_place', 'Return_flight_numb', 'Return_date', 'Return_hours',
                      'Return_changes', 'Return_flight_time', 'Price', 'Updated')

    except Exception as err:
        print('Something went wrong...: ', str(err))

    return render_template('flights_results.html',
                           the_title = 'Flight Search Engine', 
                           the_row_titles = titles,
                           the_data = contents)


@app.route('/change_app_param')
def change_app_param_page() -> 'html':
    return render_template('change_app_param.html',
                           the_title='Flight Search Engine',
                           the_search_delay = app.config['searchengineconfig']['search_delay'])


@app.route('/change_app_param_data', methods=['POST'])
def change_app_param_data() -> 'html':
    app.config['searchengineconfig']['search_delay'] = request.form['search_delay']
    with open('search_engine_config.pkl', 'wb') as search_engine_config:
        pickle.dump(app.config['searchengineconfig'], search_engine_config)
    return change_app_param_page()


@app.route('/change_flight_search')
def change_flight_search_page() -> 'html':
    return render_template('change_flight_search.html',
                           the_title='Flight Search Engine',
                           the_src_airport = app.config['flightsconfig']['srcAirport'],
                           the_dst_airport = app.config['flightsconfig']['dstAirport'],
                           the_dep_date = app.config['flightsconfig']['depdate'],
                           the_arr_date = app.config['flightsconfig']['arrdate'],
                           the_min_days = app.config['flightsconfig']['minDaysStay'],
                           the_max_days = app.config['flightsconfig']['maxDaysStay'],
                           the_adults = app.config['flightsconfig']['adults'],
                           the_children = app.config['flightsconfig']['children'],
                           the_infants = app.config['flightsconfig']['infants'],
                           the_changes = app.config['flightsconfig']['maxChng'],
                           the_currency = app.config['flightsconfig']['currency'] )

@app.route('/change_flight_search_data', methods=['POST'])
def change_flight_search_data() -> 'html':
    app.config['flightsconfig']['srcAirport'] = request.form['srcAirport']
    app.config['flightsconfig']['dstAirport'] = request.form['dstAirport']
    app.config['flightsconfig']['depdate'] = request.form['depdate']
    app.config['flightsconfig']['arrdate'] = request.form['arrdate']
    app.config['flightsconfig']['minDaysStay'] = request.form['minDaysStay']
    app.config['flightsconfig']['maxDaysStay'] = request.form['maxDaysStay']
    app.config['flightsconfig']['adults'] = request.form['adults']
    app.config['flightsconfig']['children'] = request.form['children']
    app.config['flightsconfig']['infants'] = request.form['infants']
    app.config['flightsconfig']['maxChng'] = request.form['maxChng']
    app.config['flightsconfig']['currency'] = request.form['currency']

    with open('flights_config.pkl', 'wb') as flights_config:
        pickle.dump(app.config['flightsconfig'], flights_config)

    return change_flight_search_page()


@app.route('/change_db')
def change_db_page() -> 'html':
    return render_template('change_db.html',
                           the_title='Flight Search Engine',
                           the_host = app.config['dbconfig']['host'],
                           the_user = app.config['dbconfig']['user'],
                           the_password = app.config['dbconfig']['password'],
                           the_database = app.config['dbconfig']['database'], )

@app.route('/change_db_data', methods=['POST'])
def change_db_data() -> 'html':
    app.config['dbconfig']['host'] = request.form['host_name']
    app.config['dbconfig']['user'] = request.form['user_name']
    app.config['dbconfig']['password'] = request.form['password_name']
    app.config['dbconfig']['database'] = request.form['database_name']

    with open('db_config.pkl', 'wb') as db_config:
        pickle.dump(app.config['dbconfig'], db_config)

    return change_db_page()

@app.route('/filter_flights')
def filter_flights() -> 'html':
    return render_template('filter_flights.html',
                           the_title = 'Flight Search Engine')\

@app.route('/filter_results', methods=['POST'])
def filter_flights_results() -> 'html':
    flight_price = request.form['max_price']
    titles = ('Departure_place', 'Departure_flight_numb', 'Departure_date',
              'Departure_hours', 'Departure_changes', 'Departure_flight_time',
              'Destination_place', 'Return_flight_numb', 'Return_date', 'Return_hours',
              'Return_changes', 'Return_flight_time', 'Price', 'Updated')
    try:
        with UseDatabase(app.config['dbconfig']) as cursor:
            _SQL = 'SHOW TABLES'
            cursor.execute(_SQL)
            contents = cursor.fetchall()
            flights_routes = [route[0] for route in contents]
            filtered_flights_results = []

            for flight_route in flights_routes:
                _SQL = """SELECT `Departure_place`, `Departure_flight_numb`, `Departure_date`, 
                      `Departure_hours`, `Departure_changes`, `Departure_flight_time`, 
                      `Destination_place`, `Return_flight_numb`, `Return_date`, `Return_hours`, 
                      `Return_changes`, `Return_flight_time`, `Price`, `ts` FROM `""" + flight_route + '` ' + 'WHERE Price <=' + flight_price + ' ORDER BY Price'
                cursor.execute(_SQL)
                contents = cursor.fetchall()
                if(len(contents) != 0):
                    filtered_flights_results.append(contents)

    except Exception as err:
        print('Something went wrong...: ', str(err))

    return render_template('filter_results.html',
                           the_title = 'Flight Search Engine',
                           the_max_price = flight_price,
                           the_row_titles = titles,
                           the_data_tables = filtered_flights_results)

@app.route('/delete_flights')
def delete_flights_page() -> 'html':
    return render_template('delete_flights.html',
                           the_title='Flight Search Engine')


@app.route('/delete_flights_data', methods=['POST'])
def delete_flights_data() -> 'html':

    if request.method == 'POST':
        if request.form['delete_btn'] == 'DELETE ALL':
            with UseDatabase(app.config['dbconfig']) as cursor:
                _SQL = 'SHOW TABLES'
                cursor.execute(_SQL)
                contents = cursor.fetchall()
                flights_routes = [route[0] for route in contents]
                _SQL = 'DROP TABLES'
                for flights_route in flights_routes:
                    if flights_route == flights_routes[0]:
                        _SQL += ' `' + flights_route + '`'
                    else:
                        _SQL += ', `' + flights_route + '`'
                cursor.execute(_SQL)


        elif request.form['delete_btn'] == 'DELETE TABLES':
            with UseDatabase(app.config['dbconfig']) as cursor:
                _SQL = 'SHOW TABLES WHERE Tables_in_'+app.config['dbconfig']['database'] + ' LIKE ' + """
                \'%""" + request.form['arr_place'] + '%\' AND Tables_in_'+app.config['dbconfig']['database'] + ' LIKE ' + """
                \'%""" + request.form['dst_place'] + '%\''


                cursor.execute(_SQL)
                contents = cursor.fetchall()
                flights_routes = [route[0] for route in contents]
                _SQL = 'DROP TABLES'
                for flights_route in flights_routes:
                    if flights_route == flights_routes[0]:
                        _SQL += ' `' + flights_route + '`'
                    else:
                        _SQL += ', `' + flights_route + '`'
                cursor.execute(_SQL)

    return delete_flights_page()


if __name__ == '__main__':
    app.run(debug=True, use_reloader = False)