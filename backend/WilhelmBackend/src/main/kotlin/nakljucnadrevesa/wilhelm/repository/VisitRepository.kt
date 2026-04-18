package nakljucnadrevesa.wilhelm.repository

import nakljucnadrevesa.wilhelm.entity.Patient
import nakljucnadrevesa.wilhelm.entity.Visit
import org.springframework.data.jpa.repository.JpaRepository
import org.springframework.stereotype.Repository
import java.time.LocalDate

@Repository
interface VisitRepository : JpaRepository<Visit, Long> {
    fun findByPatient(patient: Patient): List<Visit>
    fun findByPatientAndVisitDate(patient: Patient, visitDate: LocalDate): List<Visit>
}
