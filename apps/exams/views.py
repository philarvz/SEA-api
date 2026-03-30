from django.http import HttpResponse
import openpyxl
from openpyxl.styles import Font, Alignment
from io import BytesIO
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse
from drf_spectacular.types import OpenApiTypes


class QuestionTemplateDownloadView(APIView):
    """
    View to generate and download a question template Excel file
    """
    @extend_schema(
        summary="Descargar Plantilla de Preguntas", 
        description="Genera y descarga un archivo Excel con una plantilla para ingresar preguntas de examen.",
        responses={
            200: OpenApiTypes.BINARY,
            400: OpenApiResponse(description="Solicitud inválida")
        }
    )
    def get(self, request, *args, **kwargs):
        # Create a new workbook and select the active worksheet
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Plantilla de Preguntas"

        # Define headers
        headers = [
            "Materia",
            "Enunciado de la Pregunta",
            "Nivel Bloom",
            "Respuesta 1",
            "¿Es Correcta 1?",
            "Respuesta 2",
            "¿Es Correcta 2?",
            "Respuesta 3",
            "¿Es Correcta 3?",
            "Respuesta 4",
            "¿Es Correcta 4?",
            "Respuesta 5",
            "¿Es Correcta 5?"
        ]

        # Add headers to the first row
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')

        # Add some example data in the second row
        example_data = [
            "Matemáticas",
            "¿Cuál es la capital de Francia?",
            "remember",
            "París",
            "VERDADERO",
            "Londres",
            "FALSO",
            "Madrid",
            "FALSO",
            "Roma",
            "FALSO",
            "Berlín",
            "FALSO"
        ]

        for col_num, value in enumerate(example_data, 1):
            cell = ws.cell(row=2, column=col_num, value=value)
            cell.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)

        # Add instructions in the third row
        instructions = [
            "INSTRUCCIONES:",
            "1. Complete los campos requeridos para cada pregunta",
            "2. El campo 'Materia' debe coincidir con una materia existente",
            "3. Los niveles Bloom válidos son: remember, understand, apply, analyze, evaluate, create",
            "4. Para las respuestas, use VERDADERO/FALSO en la columna '¿Es Correcta?'",
            "5. Al menos una respuesta debe ser VERDADERO por pregunta",
            "6. Puede dejar respuestas en blanco si no son necesarias"
        ]

        for col_num, instruction in enumerate(instructions, 1):
            if col_num <= len(headers):
                cell = ws.cell(row=3, column=col_num, value=instruction)
                cell.font = Font(italic=True, color="666666")
                cell.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)

        # Auto-adjust column widths
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except (TypeError, AttributeError):
                    pass
            adjusted_width = min(max_length + 2, 50)  # Max width of 50
            ws.column_dimensions[column].width = adjusted_width

        # Set row height for better readability
        ws.row_dimensions[1].height = 30
        ws.row_dimensions[2].height = 40
        ws.row_dimensions[3].height = 60

        # Create response
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="plantilla_preguntas.xlsx"'

        # Save workbook to response
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        response.write(buffer.getvalue())
        buffer.close()

        return response
