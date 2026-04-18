package nakljucnadrevesa.wilhelm.exception

class PatientNotFoundException(ehrId: String) :
    RuntimeException("Patient with EHR ID '$ehrId' not found")

class PatientAlreadyExistsException(ehrId: String) :
    RuntimeException("Patient with EHR ID '$ehrId' already exists")

class VisitNotFoundException(visitId: Long) :
    RuntimeException("Visit with ID $visitId not found")

class DocumentNotFoundException(visitId: Long, filename: String) :
    RuntimeException("Document '$filename' not found for visit $visitId")

class DocumentAlreadyExistsException(filename: String, visitId: Long) :
    RuntimeException("File '$filename' already exists for visit $visitId")

class DocumentStorageException(message: String, cause: Throwable? = null) :
    RuntimeException(message, cause)
