from flask import Flask, request, redirect, url_for, render_template
import os
import redis
import socket
import logging
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace.tracer import Tracer
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.ext.flask.flask_middleware import FlaskMiddleware

# Flask application
app = Flask(__name__)

# Load configurations from environment or config file
app.config.from_pyfile('config_file.cfg')

# App Insights configuration
instrumentation_key = app.config['MYAPP_INSIGHTS_INSTRUMENTATION_KEY']

# Logging setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(AzureLogHandler(connection_string=f'InstrumentationKey={instrumentation_key}'))

# Tracing setup
tracer = Tracer(exporter=AzureExporter(connection_string=f'InstrumentationKey={instrumentation_key}'),
                sampler=ProbabilitySampler(1.0))

# Middleware for tracing requests
middleware = FlaskMiddleware(app, 
                              exporter=AzureExporter(connection_string=f'InstrumentationKey={instrumentation_key}'),
                              sampler=ProbabilitySampler(1.0))

# Redis configuration
redis_host = 'localhost'
redis_port = 6380
r = redis.Redis(host=redis_host, port=redis_port)

# Load environment variables or default configuration
button1 = os.getenv('VOTE1VALUE', app.config['VOTE1VALUE'])
button2 = os.getenv('VOTE2VALUE', app.config['VOTE2VALUE'])
title = os.getenv('TITLE', app.config['TITLE'])

# Display hostname in title if enabled
if app.config['SHOWHOST'] == "true":
    title = socket.gethostname()

# Initialize Redis keys if not already set
if not r.get(button1): r.set(button1, 0)
if not r.get(button2): r.set(button2, 0)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        vote = request.form.get('vote')

        if vote == 'reset':
            # Reset vote my counts to zero
            r.set(button1, 0)
            r.set(button2, 0)

            # khs Log reset 
            logger.info('Votes reset', extra={'custom_dimensions': {'Cats Vote': 0, 'Dogs Vote': 0}})
        else:
            # Increment the selected vote
            r.incr(vote, 1)

            # Log vote action with distinct custom events
            if vote == button1:
                logger.info('Cats Vote')
            elif vote == button2:
                logger.info('Dogs Vote')
        # Redirect to avoid form re-submission on page reload
        return redirect(url_for('index'))

    # GET request: retrieve current vote counts
    vote1 = int(r.get(button1).decode('utf-8'))
    vote2 = int(r.get(button2).decode('utf-8'))

    # Trace vote retrieval
    with tracer.span(name="GET /index - Retrieve Votes") as span:
        span.add_attribute("Cats Vote", vote1)
        span.add_attribute("Dogs Vote", vote2)

    # Render the template
    return render_template("index.html", value1=vote1, value2=vote2, button1=button1, button2=button2, title=title)

if __name__ == "__main__":
    # Local development
    #app.run(debug=True)
    app.run(host='0.0.0.0', port=5000)
    # Deployment (uncomment for production)
    # app.run(host='0.0.0.0', threaded=True, debug=True)
