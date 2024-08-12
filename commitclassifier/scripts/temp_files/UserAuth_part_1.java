// Extracted from /mnt/c/Users/HP/slab/ai4fix/semo-project/src/main/java/UserAuth.java, lines 1-39
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HashMap;
import java.util.Map;

public class UserAuth {
    private static Map<String, String> usersDatabase = new HashMap<>();


    private static String hashPassword(String password) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] hashedPassword = md.digest(password.getBytes());
            StringBuilder sb = new StringBuilder();
            for (byte b : hashedPassword) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new RuntimeException("Error hashing password", e);
        }
    }

    public static void registerUser(String username, String password) {
        String hashedPassword = hashPassword(password);
        usersDatabase.put(username, hashedPassword);
    }

    public static boolean authenticateUser(String username, String password) {
        String storedHashedPassword = usersDatabase.get(username);
        return storedHashedPassword != null && storedHashedPassword.equals(hashPassword(password));
    }

    public static void main(String[] args) {
        registerUser("user1", "password123");
        boolean isAuthenticated = authenticateUser("user1", "password123");
        System.out.println("Authentication successful: " + isAuthenticated);
    }
}
