#
# entity.py -- various entities used by queue system
#
# Russell Kackley (rkackley@naoj.org)
# Eric Jeschke (eric@naoj.org)
#
import csv
import string
import StringIO

import entity
from ginga.misc import Bunch


class QueueFile(object):

    # Default format parameters for reading/writing CSV files.
    fmtparams = {'delimiter':',', 'quotechar':'"', 'quoting': csv.QUOTE_MINIMAL}

    def __init__(self, filepath, logger, column_map, **parse_kwdargs):
        self.filepath = filepath
        self.logger = logger
        self.queue_file = None
        self.columnNames = []
        self.rows = []
        self.parse_kwdargs = parse_kwdargs
        self.column_map = column_map

        # Read the supplied filepath into a StringIO object. This
        # makes it easier to process and parse the file contents with
        # the CSV classes.
        with open(filepath, 'rb') as f:
            self.queue_file = StringIO.StringIO(f.read())

        # Read and save the first line, which should have the column
        # titles.
        reader = csv.reader(self.queue_file, **self.fmtparams)
        self.columnNames = next(reader)

        # Read the rest of the file and put the contents into a list
        # data structure (i.e., the "rows" attribute). The column
        # titles will be the dictionary keys.
        reader = csv.DictReader(self.queue_file.getvalue().splitlines(),
                                **self.fmtparams)
        for row in reader:
            self.rows.append(row)

        self.parse_input()
        # We are done with the StringIO object, so close it.
        self.queue_file.close()

    def write_output(self, new_filepath=None):
        # Write the data to the specified output file. If a
        # new_filepath is supplied, use it. Otherwise, use the
        # existing filepath.
        if new_filepath:
            self.filepath = new_filepath

        # Open the file for writing.
        with open(self.filepath, 'wb') as f:
            # Write the column titles first
            writer = csv.writer(f, **self.fmtparams)
            writer.writerow(self.columnNames)

            # Write the rest of the file from the "rows" attribute,
            # which stores the data as a list of dictionaries.
            writer = csv.DictWriter(f, self.columnNames, **self.fmtparams)
            for row in self.rows:
                writer.writerow(row)

    def parse_input(self):
        # Override in subclass
        pass

    def update(self, row, colHeader, value, parse_flag):
        # User has changed a value in the table, so update our "rows"
        # attribute, recreate the StringIO object, and parse the input
        # again.
        self.logger.debug('QueueFile.update row %d colHeader %s value %s' % (row, colHeader, value))
        self.rows[row][colHeader] = value

        # Use the CSV "writer" classes to create a new version of the
        # StringIO object from our "rows" attribute.
        if parse_flag:
            self.parse()

    def parse(self):
        # Create a StringIO.StringIO object and write our columnNames
        # and rows attributes into that object. This gives us an
        # object that looks like a disk file so we can parse the data.
        self.queue_file = StringIO.StringIO()
        writer = csv.writer(self.queue_file, **self.fmtparams)
        writer.writerow(self.columnNames)
        writer = csv.DictWriter(self.queue_file, self.columnNames, **self.fmtparams)
        for row in self.rows:
            writer.writerow(row)

        # Parse the input data from the StringIO.StringIO object
        try:
            self.parse_input()

        except Exception as e:
            self.logger.error("Error reparsing input: %s" % (str(e)))
            
        # We are done with the StringIO object, so close it.
        self.queue_file.close()

    def parse_row(self, row):
        # Parse a row of values (tup or list) into a record that can
        # be accessed by attribute or map key
        rec = Bunch.Bunch()
        for i in range(len(row)):
            if i >= len(self.columnNames):
                break
            # mangle header to get column->attribute mapping key
            colname = self.columnNames[i]
            key = colname.strip().lower().replace(' ', '_')
            # get attr key
            if not key in self.column_map:
                self.logger.warn("No column->record map entry for column '%s' (%s); skipping..." % (colname, key))
                continue
            attrkey = self.column_map[key]
            rec[attrkey] = row[i]
        return rec


class ScheduleFile(QueueFile):
    def __init__(self, filepath, logger):
        # schedule_info is the list of tuples that will be used by the
        # observing block scheduling functions.
        self.schedule_info = []
        column_map = {
            'date': 'date',
            'start_time': 'starttime',
            'end_time': 'stoptime',
            'categories': 'categories',
            'filters': 'filters',
            'sky': 'skycond',
            'avg_seeing': 'seeing',
            'note': 'note',
            }
        super(ScheduleFile, self).__init__(filepath, logger, column_map)


    def parse_input(self):
        """
        Parse the observing schedule from the input file.
        """
        self.queue_file.seek(0)
        self.schedule_info = []
        reader = csv.reader(self.queue_file, **self.fmtparams)
        # skip header
        next(reader)

        lineNum = 1
        for row in reader:
            try:
                lineNum += 1
                # skip comments
                if row[0].lower() == 'comment':
                    continue
                # skip blank lines
                if len(row[0].strip()) == 0:
                    continue

                rec = self.parse_row(row)
                self.logger.debug('ScheduleFile.parse_input rec %s' % (rec))

            except Exception as e:
                raise ValueError("Error reading line %d of schedule: %s" % (
                    lineNum, str(e)))

            filters = list(map(string.strip, rec.filters.lower().split(',')))
            seeing = float(rec.seeing)
            categories = rec.categories.replace(' ', '').lower().split(',')
            skycond = rec.skycond.lower()

            # TEMP: skip non-OPEN categories
            if not 'open' in categories:
                continue

            rec2 = Bunch.Bunch(date=rec.date, starttime=rec.starttime,
                               stoptime=rec.stoptime,
                               categories=categories, filters=filters,
                               seeing=seeing, skycond=skycond, note=rec.note)
            self.schedule_info.append(rec2)


class ProgramsFile(QueueFile):
    def __init__(self, filepath, logger):
        # programs_info is the dictionary of Program objects that will
        # be used by the observing block scheduling functions.
        self.programs_info = {}
        column_map = {
            'proposal': 'proposal',
            'propid': 'propid',
            'rank': 'rank',
            'category': 'category',
            'instruments': 'instruments',
            'band': 'band',
            'hours': 'hours',
            'partner': 'partner',
            'skip': 'skip',
            }
        super(ProgramsFile, self).__init__(filepath, logger, column_map)

    def parse_input(self):
        """
        Parse the programs from the input file.
        """
        self.queue_file.seek(0)
        old_info = self.programs_info
        self.programs_info = {}
        reader = csv.reader(self.queue_file, **self.fmtparams)
        # skip header
        next(reader)

        lineNum = 1
        for row in reader:
            try:
                lineNum += 1
                # skip comments
                if row[0].lower() == 'comment':
                    continue
                # skip blank lines
                if len(row[0].strip()) == 0:
                    continue

                rec = self.parse_row(row)
                if rec.skip.strip() != '':
                    continue

                key = rec.proposal.upper()
                pgm = entity.Program(key, propid=rec.propid,
                                     rank=float(rec.rank),
                                     band=int(rec.band),
                                     partner=rec.partner,
                                     category=rec.category,
                                     instruments=rec.instruments.upper().split(','),
                                     hours=float(rec.hours))
                
                # update existing old program record if it exists
                # since OBs may be pointing to it
                if key in old_info:
                    new_pgm = pgm
                    pgm = old_info[key]
                    pgm.__dict__.update(new_pgm.__dict__)

                self.programs_info[key] = pgm

            except Exception as e:
                raise ValueError("Error reading line %d of programs: %s" % (
                    lineNum, str(e)))


class WeightsFile(QueueFile):

    def __init__(self, filepath, logger):

        self.weights = Bunch.Bunch()
        column_map = {
            'slew': 'w_slew',
            'delay': 'w_delay',
            'filter': 'w_filterchange',
            'rank': 'w_rank',
            'priority': 'w_priority',
            }
        super(WeightsFile, self).__init__(filepath, logger, column_map)

    def parse_input(self):
        """
        Parse the weights from the input file.
        """
        self.queue_file.seek(0)
        self.weights = Bunch.Bunch()
        reader = csv.reader(self.queue_file, **self.fmtparams)
        # skip header
        next(reader)

        lineNum = 1
        for row in reader:
            try:
                lineNum += 1
                # skip comments
                if row[0].lower() == 'comment':
                    continue
                # skip blank lines
                if len(row[0].strip()) == 0:
                    continue

                rec = self.parse_row(row)
                ## if rec.skip.strip() != '':
                ##     continue

                # remember the last one read
                zipped = rec.items()
                keys, vals = zip(*zipped)
                self.weights = Bunch.Bunch(zip(keys, map(float, vals)))

            except Exception as e:
                raise ValueError("Error reading line %d of weights: %s" % (
                    lineNum, str(e)))


class TelCfgFile(QueueFile):
    def __init__(self, filepath, logger):
        self.tel_cfgs = {}
        column_map = {
            'id': 'id',
            'foci': 'focus',
            'comment': 'comment',
            }
        super(TelCfgFile, self).__init__(filepath, logger, column_map)

    def parse_input(self):
        """
        Read all telescope configurations from a CSV file.
        """
        self.queue_file.seek(0)
        self.tel_cfgs = Bunch.caselessDict()
        reader = csv.reader(self.queue_file, **self.fmtparams)
        # skip header
        next(reader)

        lineNum = 1
        for row in reader:
            try:
                lineNum += 1

                # skip comments
                if row[0].lower() == 'comment':
                    continue
                # skip blank lines
                if len(row[0].strip()) == 0:
                    continue

                rec = self.parse_row(row)
                cfgid = rec.id.strip()
                telcfg = entity.TelescopeConfiguration(focus=rec.focus)

                self.tel_cfgs[cfgid] = telcfg

            except Exception as e:
                raise ValueError("Error reading line %d of telcfgs from file %s: %s" % (
                    lineNum, self.filepath, str(e)))


class EnvCfgFile(QueueFile):
    def __init__(self, filepath, logger):
        self.env_cfgs = {}
        column_map = {
            'code': 'code',
            'seeing': 'seeing',
            'airmass': 'airmass',
            'moon': 'moon',
            'sky': 'sky',
            'comment': 'comment',
            }
        super(EnvCfgFile, self).__init__(filepath, logger, column_map)

    def parse_input(self):
        """
        Read all environment configurations from a CSV file.
        """
        self.queue_file.seek(0)
        self.env_cfgs = Bunch.caselessDict()
        reader = csv.reader(self.queue_file, **self.fmtparams)
        # skip header
        next(reader)

        lineNum = 1
        for row in reader:
            try:
                lineNum += 1

                # skip comments
                if row[0].lower() == 'comment':
                    continue
                # skip blank lines
                if len(row[0].strip()) == 0:
                    continue

                rec = self.parse_row(row)
                code = rec.code.strip()

                seeing = rec.seeing.strip()
                if len(seeing) != 0:
                    seeing = float(seeing)
                else:
                    seeing = None

                airmass = rec.airmass.strip()
                if len(airmass) != 0:
                    airmass = float(airmass)
                else:
                    airmass = None

                moon = rec.moon
                sky = rec.sky

                envcfg = entity.EnvironmentConfiguration(seeing=seeing,
                                                         airmass=airmass,
                                                         moon=moon, sky=sky)
                self.env_cfgs[code] = envcfg

            except Exception as e:
                raise ValueError("Error reading line %d of oblist from file %s: %s" % (
                    lineNum, self.filepath, str(e)))


class TgtCfgFile(QueueFile):
    def __init__(self, filepath, logger):
        self.tgt_cfgs = {}
        column_map = {
            'code': 'code',
            'target_name': 'name',
            'ra': 'ra',
            'dec': 'dec',
            'equinox': 'eq',
            'comment': 'comment',
            }
        super(TgtCfgFile, self).__init__(filepath, logger, column_map)

    def parse_input(self):
        """
        Read all target configurations from a CSV file.
        """
        self.queue_file.seek(0)
        self.tgt_cfgs = Bunch.caselessDict()
        reader = csv.reader(self.queue_file, **self.fmtparams)
        # skip header
        next(reader)

        lineNum = 1
        for row in reader:
            try:
                lineNum += 1

                # skip comments
                if row[0].lower() == 'comment':
                    continue
                # skip blank lines
                if len(row[0].strip()) == 0:
                    continue

                rec = self.parse_row(row)
                code = rec.code.strip()

                # transform equinox, e.g. "J2000" -> 2000
                eq = rec.eq
                if isinstance(eq, str):
                    eq = eq.upper()
                    if eq[0] in ('B', 'J'):
                        eq = eq[1:]
                        eq = float(eq)
                eq = int(eq)

                target = entity.StaticTarget(rec.name, rec.ra, rec.dec, eq)
                self.tgt_cfgs[code] = target

            except Exception as e:
                raise ValueError("Error reading line %d of oblist from file %s: %s" % (
                    lineNum, self.filepath, str(e)))


class InsCfgFile(QueueFile):
    def __init__(self, filepath, logger):
        self.ins_cfgs = {}
        column_map = {
            'code': 'code',
            'instrument': 'inst',
            'mode': 'mode',
            'filter': 'filter',
            'exp_time': 'exp_time',
            'num_exp': 'num_exp',
            'dither': 'dither',
            'guiding': 'guiding',
            'pa': 'pa',
            'offset_ra': 'offset_ra',
            'offset_dec': 'offset_dec',
            'dither_ra': 'dither_ra',
            'dither_dec': 'dither_dec',
            'binning': 'binning',
            'comment': 'comment',
            }
        super(InsCfgFile, self).__init__(filepath, logger, column_map)

    def parse_input(self):
        """
        Read all instrument configurations from a CSV file.
        """
        self.queue_file.seek(0)
        self.ins_cfgs = Bunch.caselessDict()
        reader = csv.reader(self.queue_file, **self.fmtparams)
        # skip header
        next(reader)

        lineNum = 1
        for row in reader:
            try:
                lineNum += 1

                # skip comments
                if row[0].lower() == 'comment':
                    continue
                # skip blank lines
                if len(row[0].strip()) == 0:
                    continue

                rec = self.parse_row(row)
                code = rec.code.strip()
                
                filtername = rec.filter
                if 'SPCAM' in rec.inst.upper():
                    guiding = ('Y' == rec.guiding)
                    mode = rec.mode
                    inscfg = entity.SPCAMConfiguration(filter=filtername,
                                                mode=mode, guiding=guiding,
                                                num_exp=int(rec.num_exp),
                                                exp_time=int(rec.exp_time),
                                                pa=rec.pa,
                                                offset_ra=rec.offset_ra,
                                                offset_dec=rec.offset_dec,
                                                dith1=rec.dither_ra,
                                                dith2=rec.dither_dec)
                elif 'FOCAS' in rec.inst.upper():
                    guiding = ('Y' == rec.guiding)
                    mode = rec.mode
                    inscfg = entity.FOCASConfiguration(filter=filtername,
                                                mode=mode, guiding=guiding,
                                                num_exp=int(rec.num_exp),
                                                exp_time=int(rec.exp_time),
                                                pa=float(rec.pa),
                                                offset_ra=rec.offset_ra,
                                                offset_dec=rec.offset_dec,
                                                dither_ra=rec.dither_ra,
                                                dither_dec=rec.dither_dec,
                                                binning=rec.binning)
                else:
                    raise ValueError("No valid instruments listed")

                self.ins_cfgs[code] = inscfg

            except Exception as e:
                raise ValueError("Error reading line %d of instrument configuration from file %s: %s" % (
                    lineNum, self.filepath, str(e)))



class OBListFile(QueueFile):
    def __init__(self, filepath, logger, propname, propdict,
                 telcfgs, tgtcfgs, inscfgs, envcfgs):
        # obs_info is the list of OB objects that will be used by the
        # observing block scheduling functions.
        self.obs_info = []
        self.proposal = propname.upper()
        # lookup tables
        self.propdict = propdict
        self.telcfgs = telcfgs
        self.tgtcfgs = tgtcfgs
        self.inscfgs = inscfgs
        self.envcfgs = envcfgs

        column_map = {
            'id': 'id',
            'code': 'code',
            'tgtcfg': 'tgt_code',
            'inscfg': 'ins_code',
            'telcfg': 'tel_code',
            'envcfg': 'env_code',
            'priority': 'priority',
            'total_time': 'total_time',
            'comment': 'comment',
            }
        super(OBListFile, self).__init__(filepath, logger, column_map)

    def parse_input(self):
        """
        Read all observing blocks from a CSV file.
        """
        self.queue_file.seek(0)
        self.obs_info = []
        reader = csv.reader(self.queue_file, **self.fmtparams)
        # skip header
        next(reader)

        lineNum = 1
        for row in reader:
            try:
                lineNum += 1

                # skip comments
                if row[0].lower() == 'comment':
                    continue
                # skip blank lines
                if len(row[0].strip()) == 0:
                    continue

                rec = self.parse_row(row)
                code = rec.code.strip()

                program = self.propdict[self.proposal]
                envcfg = self.envcfgs[rec.env_code.strip()]
                telcfg = self.telcfgs[rec.tel_code.strip()]
                tgtcfg = self.tgtcfgs[rec.tgt_code.strip()]
                inscfg = self.inscfgs[rec.ins_code.strip()]

                priority = 1.0
                if rec.priority != None:
                    priority = float(rec.priority)
                    
                ob = entity.OB(program=program,
                               target=tgtcfg,
                               inscfg=inscfg,
                               envcfg=envcfg,
                               telcfg=telcfg,
                               priority=priority,
                               name=code,
                               total_time=float(rec.total_time))
                self.obs_info.append(ob)

            except Exception as e:
                raise ValueError("Error reading line %d of oblist from file %s: %s" % (
                    lineNum, self.filepath, str(e)))



#END