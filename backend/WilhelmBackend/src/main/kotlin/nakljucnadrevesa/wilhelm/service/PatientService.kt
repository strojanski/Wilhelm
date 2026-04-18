package nakljucnadrevesa.wilhelm.service

import nakljucnadrevesa.wilhelm.dto.CreatePatientRequest
import nakljucnadrevesa.wilhelm.dto.PatientResponse
import nakljucnadrevesa.wilhelm.dto.toResponse
import nakljucnadrevesa.wilhelm.entity.Patient
import nakljucnadrevesa.wilhelm.exception.DocumentStorageException
import nakljucnadrevesa.wilhelm.exception.PatientAlreadyExistsException
import nakljucnadrevesa.wilhelm.exception.PatientNotFoundException
import nakljucnadrevesa.wilhelm.repository.PatientRepository
import org.springframework.beans.factory.annotation.Value
import org.springframework.data.domain.Page
import org.springframework.data.domain.Pageable
import org.springframework.stereotype.Service
import java.io.IOException
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths

@Service
class PatientService(
    private val patientRepository: PatientRepository,
    @Value("\${app.reports.directory}") private val reportsDir: String
) {

    fun createPatient(request: CreatePatientRequest): PatientResponse {
        if (patientRepository.findByEhrId(request.ehrId).isPresent) {
            throw PatientAlreadyExistsException(request.ehrId)
        }
        val patient = patientRepository.save(
            Patient(
                firstName = request.firstName,
                lastName = request.lastName,
                ehrId = request.ehrId,
                age = request.age,
                gender = request.gender
            )
        )
        try {
            Files.createDirectories(patientFolder(patient.ehrId))
        } catch (ex: IOException) {
            throw DocumentStorageException("Failed to create folder for patient '${patient.ehrId}'", ex)
        }
        return patient.toResponse()
    }

    fun getAllPatients(pageable: Pageable): Page<PatientResponse> =
        patientRepository.findAll(pageable).map { it.toResponse() }

    fun getPatient(ehrId: String): PatientResponse =
        findOrThrow(ehrId).toResponse()

    fun deletePatient(ehrId: String) {
        val patient = findOrThrow(ehrId)
        try {
            patientFolder(patient.ehrId).toFile().deleteRecursively()
        } catch (ex: IOException) {
            throw DocumentStorageException("Failed to delete folder for patient '$ehrId'", ex)
        }
        patientRepository.delete(patient)
    }

    fun patientFolder(ehrId: String): Path =
        Paths.get(reportsDir).toAbsolutePath().resolve(ehrId)

    fun findOrThrow(ehrId: String): Patient =
        patientRepository.findByEhrId(ehrId)
            .orElseThrow { PatientNotFoundException(ehrId) }
}
