package nakljucnadrevesa.wilhelm.repository

import nakljucnadrevesa.wilhelm.entity.Patient
import org.springframework.data.jpa.repository.JpaRepository
import org.springframework.stereotype.Repository
import java.util.Optional

@Repository
interface PatientRepository : JpaRepository<Patient, Long> {
    fun findByEhrId(ehrId: String): Optional<Patient>
}
