import collections

from django.core.management.base import BaseCommand, CommandError

from respondants.models import Institution, ParentInstitution

#Let's try out named tuples.
ReporterRow = collections.namedtuple(
    "ReporterRow",
    [
        'year',
        'respondant_id',
        'agency_code',
        'parent_id',
        'parent_name',
        'parent_city',
        'parent_state',
        'region',
        'assets',
        'lender_code',
        'respondant_name',
        'filler_1',
        'respondant_city',
        'respondant_state',
        'filler_2',
        'filler_3',
        'top_holder_rssd_id',
        'top_holder_name',
        'top_holder_city',
        'top_holder_state',
        'top_holder_country',
        'respondant_rssd_id',
        'parent_rssd_id',
        'respondant_fips_state'
    ]
)


def parse_line(line):
    """ Parse a reporter panel line into a dictionary.  """
    reporter = ReporterRow(
        year=line[0:4],
        respondant_id=line[4:14],
        agency_code=int(line[14:15]),
        parent_id=line[15:25].strip(),
        parent_name=line[25:55].strip(),
        parent_city=line[55:80].strip(),
        parent_state=line[80:82],
        region=line[82:84],
        assets=line[84:94],
        lender_code=line[94:95],
        respondant_name=line[95:125],
        filler_1=line[125:165],
        respondant_city=line[165:190],
        respondant_state=line[190:192],
        filler_2=line[192:202],
        filler_3=line[202:212],
        top_holder_rssd_id=line[212:222],
        top_holder_name=line[222:252],
        top_holder_city=line[252:277],
        top_holder_state=line[277:279],
        top_holder_country=line[279:319],
        respondant_rssd_id=line[319:329],
        parent_rssd_id=line[329:339],
        respondant_fips_state=line[339:341],
    )
    return reporter


def get_institution(reporter):
    """ Get the Institution object that corresonds tot his ReporterRow. """

    institution = Institution.objects.get(
        year=reporter.year,
        agency__hmda_id=reporter.agency_code,
        ffiec_id=reporter.respondant_id)
    return institution


def get_parent(reporter):
    """ Get the parent institution based on either the HMDA ID or the
    RSSD ID. """

    parents = Institution.objects.filter(
        year=reporter.year,
        ffiec_id=reporter.parent_id,
        zip_code__state=reporter.parent_state)
    if len(parents) > 0:
        return parents[0]
    else:
        #Use the RSSD ID to look for the parent. There's at least one case
        #where the RSSD ID matches, but the FFIEC ID does not. Also, in cases
        #where the RSSD ID matches, the state does not. We'll go based on
        #RSSD ID - but that still indicates weirdness in the data.
        parents = Institution.objects.filter(
            year=reporter.year,
            rssd_id=reporter.parent_rssd_id)

        if len(parents) > 0:
            return parents[0]


def create_parent_institution(reporter):
    parent = ParentInstitution(
        year=reporter.year,
        name=reporter.parent_name,
        city=reporter.parent_city,
        state=reporter.parent_state,
        rssd_id=reporter.parent_rssd_id
    )
    parent.save()
    return parent


def get_or_create_parent(reporter):
    try:
        parent = ParentInstitution.objects.get(
            rssd_id=reporter.parent_rssd_id)
    except ParentInstitution.DoesNotExist:
        parent = create_parent_institution(reporter)
    return parent


def assign_parent(bank, reporter):
    if reporter.parent_id == '':
        bank.parent = None
    else:
        parent = get_parent(reporter)
        if parent is None:
            parent = get_or_create_parent(reporter)
            bank.non_reporting_parent = parent
        else:
            bank.parent = parent
    return bank


def process_reporter(reporters):
    """ For each institution, add the National Information Center RSSD ID. """
    for reporter in reporters:
        bank = get_institution(reporter)

        if reporter.respondant_rssd_id == '0000000000':
            bank.rssd_id = None
        else:
            bank.rssd_id = reporter.respondant_rssd_id

        bank = assign_parent(bank, reporter)
        bank.save()


def parse_file(filename):
    """ Parse the FFIEC HMDA reporterpanel.dat file. The format of this file is
    pre-determined by the FFIEC. """

    reporters = []
    with open(filename, encoding='utf-8') as panelcsv:
        for line in panelcsv:
            reporter_row = parse_line(line)
            reporters.append(reporter_row)
    return reporters


class Command(BaseCommand):
    args = "<filename>"
    help = "Reporter panel contains parent information. Loads that."

    def handle(self, *args, **options):
        reporter_filename = args[0]
        reporter_rows = parse_file(reporter_filename)
        process_reporter(reporter_rows)