from datetime import datetime
from app.models.ticket import Ticket
from app.extensions import db
from sqlalchemy import extract


from datetime import datetime
import pytz

zona_ecuador = pytz.timezone("America/Guayaquil")