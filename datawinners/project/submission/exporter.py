import logging
import resource
from datawinners.project.Header import SubmissionExcelHeader
from datawinners.project.submission.export import export_filename, create_zipped_excel_response
from datawinners.project.submission.formatter import SubmissionFormatter
from datawinners.project.submission.submission_search import get_scrolling_submissions_query

logger = logging.getLogger("datawinners")


class SubmissionExporter:
    def __init__(self, form_model, project_name, dbm, local_time_delta, current_language='en'):
        self.form_model = form_model
        self.project_name = project_name
        self.language = current_language
        self.dbm = dbm
        self.local_time_delta = local_time_delta

    def _create_response(self, columns, submission_list, submission_type):
        submission_formatter = SubmissionFormatter(columns, self.local_time_delta)

        logger.error('Before header list: %s (kb)' % resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)

        header_list= submission_formatter.format_header_data()

        logger.error('After header list fetch: %s (kb)' % resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)

        return create_zipped_excel_response(header_list, submission_list,
                                            export_filename(submission_type, self.project_name),submission_formatter)

    def create_excel_response(self, submission_type, query_params):

        logger.error('Before columns fetch: %s (kb)' % resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)

        columns = SubmissionExcelHeader(self.form_model, submission_type, self.language).get_columns()

        logger.error('After columns fetch: %s (kb)' % resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)

        search_results, query_fields = get_scrolling_submissions_query(self.dbm, self.form_model, query_params,
                                                                       self.local_time_delta)

        logger.error('Fetched cursor: %s (kb)' % resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)

        return self._create_response(columns, search_results, submission_type)