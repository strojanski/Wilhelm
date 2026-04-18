package nakljucnadrevesa.wilhelm.exception

import org.springframework.http.HttpStatus
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.ExceptionHandler
import org.springframework.web.bind.annotation.RestControllerAdvice
import java.time.Instant

data class ErrorResponse(
    val status: Int,
    val error: String,
    val message: String,
    val timestamp: Instant = Instant.now()
)

@RestControllerAdvice
class GlobalExceptionHandler {

    @ExceptionHandler(PatientNotFoundException::class)
    fun handlePatientNotFound(ex: PatientNotFoundException): ResponseEntity<ErrorResponse> =
        ResponseEntity.status(HttpStatus.NOT_FOUND).body(
            ErrorResponse(HttpStatus.NOT_FOUND.value(), "Not Found", ex.message!!)
        )

    @ExceptionHandler(PatientAlreadyExistsException::class)
    fun handlePatientAlreadyExists(ex: PatientAlreadyExistsException): ResponseEntity<ErrorResponse> =
        ResponseEntity.status(HttpStatus.CONFLICT).body(
            ErrorResponse(HttpStatus.CONFLICT.value(), "Conflict", ex.message!!)
        )

    @ExceptionHandler(VisitNotFoundException::class)
    fun handleVisitNotFound(ex: VisitNotFoundException): ResponseEntity<ErrorResponse> =
        ResponseEntity.status(HttpStatus.NOT_FOUND).body(
            ErrorResponse(HttpStatus.NOT_FOUND.value(), "Not Found", ex.message!!)
        )

    @ExceptionHandler(DocumentNotFoundException::class)
    fun handleDocumentNotFound(ex: DocumentNotFoundException): ResponseEntity<ErrorResponse> =
        ResponseEntity.status(HttpStatus.NOT_FOUND).body(
            ErrorResponse(HttpStatus.NOT_FOUND.value(), "Not Found", ex.message!!)
        )

    @ExceptionHandler(DocumentAlreadyExistsException::class)
    fun handleDocumentAlreadyExists(ex: DocumentAlreadyExistsException): ResponseEntity<ErrorResponse> =
        ResponseEntity.status(HttpStatus.CONFLICT).body(
            ErrorResponse(HttpStatus.CONFLICT.value(), "Conflict", ex.message!!)
        )

    @ExceptionHandler(DocumentStorageException::class)
    fun handleDocumentStorage(ex: DocumentStorageException): ResponseEntity<ErrorResponse> =
        ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(
            ErrorResponse(HttpStatus.INTERNAL_SERVER_ERROR.value(), "Storage Error", ex.message!!)
        )
}
