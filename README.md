# Copernicus-Explorer

Final version of the web catalogue of Sentinel imagery Copernicus-Explorer written in Python/Django

* Periodically update database using Python and SciHub API.
* Search for satellite images using spatial queries.
* Clip satellite imagery using GDAL library in order to save bandwidth.
* Asynchronous task execution using Celery and RabbitMQ.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes. See deployment for notes on how to deploy the project on a live system.

### Prerequisites

Geospatial libraries:
* GEOS
* PROJ.4
* GDAL

Databases:
* PostgreSQL 12
* PostGIS extension

Message broker:
* RabbitMQ

Python modules listed in a requirements.txt file.  

### Installing

Create a virtual environment and activate it

```shell
python3 -m venv venv
source venv/bin/activate 
```

Install GDAL using the following command 

```shell
pip install --global-option=build_ext --global-option="-I/usr/include/gdal" GDAL==`gdal-config --version`
```

Install the rest of Python modules

```shell
pip install -r requirements.txt
```

Create an empty file named .env in the root directory and configure environmental variables. Sample .env file content::

```
DEBUG=True
SECRET_KEY=1234567890abcdefghijklmnoprs

ALLOWED_HOSTS=127.0.0.1
CORS_ORIGIN_WHITELIST=http://127.0.0.1:8000

DB_NAME=cpexplorer
DB_USER=cpexplorer
DB_PASSWORD=password
DB_HOST=127.0.0.1
DB_PORT=5432
```

Create a PostgrSQL database and open the psql prompt

```shell
createdb cpexplorer
psql cpexplorer
```

Install a PostGIS extension in the database, then create a database user for the Django application and grant them access to the database:

```SQL
CREATE EXTENSION postgis;
CREATE USER django PASSWORD 'password';
GRANT CONNECT ON DATABASE ddrallye TO django;
GRANT USAGE ON SCHEMA public TO django;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO django;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO django;
```

Prepare migration files and migrate models to the database

```
python manage.py makemigrations
python manage.py migrate
```

Create Django superadmin

```shell
python manage.py createsuperuser
```

Run an app

```shell
python manage.py runserver
```

### Deployment



## Testing



## Built With

* [Django](https://docs.djangoproject.com/en/3.0/) - The web framework used

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

## Authors

* **Tomasz Przybyłek** - *Initial work* - [tprzybylek](https://github.com/tprzybylek)

See also the list of [contributors](hhttps://github.com/tprzybylek/Copernicus-Explorer/contributors) who participated in this project.

## License

This project is licensed under the GNU AGPL License - see the [LICENSE.md](LICENSE.md) file for details
