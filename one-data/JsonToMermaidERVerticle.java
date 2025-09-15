package com.axp.microdose.examples;

import com.axp.logging.schema.v0_1.Structured;
import com.axp.microdose.commons.MicrodoseConstants;
import com.axp.microdose.data.MicrodoseFunction;
import io.vertx.core.Future;
import io.vertx.core.MultiMap;
import io.vertx.core.eventbus.DeliveryOptions;
import io.vertx.core.eventbus.Message;
import io.vertx.core.json.JsonArray;
import io.vertx.core.json.JsonObject;
import org.apache.commons.lang3.StringUtils;
import org.apache.commons.lang3.exception.ExceptionUtils;
import org.apache.http.HttpStatus;

public class JsonToMermaidERVerticle extends MicrodoseFunction<JsonObject> {

    @Override
    protected Future<Void> initFunction(Structured classMarker) {
        // The below line is only needed if plan to mask PII data
        // logger = LoggerFactory.getLogger(this.getClass(), LogMaskingType.ASTERIK);
        return Future.succeededFuture();
    }

    @Override
    protected void handle(Message<JsonObject> message, Structured messageMarker) {
        try {
            var requestBody = message.body();

            logger.info(messageMarker, "Received JSON to Mermaid ER conversion request: {}", requestBody);
            if (!isRequestValid(message, messageMarker)) {
                return;
            }

            String mermaidDiagram = convertJsonToMermaidER(requestBody, messageMarker);

            MultiMap headers = MultiMap.caseInsensitiveMultiMap();
            headers.set(MicrodoseConstants.HTTP_STATUS_CODE, String.valueOf(HttpStatus.SC_OK));
            headers.set("Content-Type", "text/markdown");
            
            DeliveryOptions replyOptions = new DeliveryOptions().setHeaders(headers);
            message.reply(mermaidDiagram, replyOptions);
        } catch (Exception e) {
            logger.error(messageMarker, "JSON to Mermaid ER conversion failed: {}", ExceptionUtils.getStackTrace(e));
            message.fail(HttpStatus.SC_INTERNAL_SERVER_ERROR, "Internal server error: " + ExceptionUtils.getStackTrace(e));
        }
    }

    private String convertJsonToMermaidER(JsonObject jsonData, Structured messageMarker) {
        StringBuilder mermaid = new StringBuilder();
        mermaid.append("```mermaid\n");
        mermaid.append("erDiagram\n");

        // Extract entities and relationships from JSON
        JsonArray entities = jsonData.getJsonArray("entities");
        JsonArray relationships = jsonData.getJsonArray("relationships");

        // Process entities
        if (entities != null) {
            for (Object entityObj : entities) {
                JsonObject entity = (JsonObject) entityObj;
                String entityName = entity.getString("name");
                JsonArray attributes = entity.getJsonArray("attributes");

                mermaid.append("    ").append(entityName).append(" {\n");
                
                if (attributes != null) {
                    for (Object attrObj : attributes) {
                        JsonObject attr = (JsonObject) attrObj;
                        String attrName = attr.getString("name");
                        String attrType = attr.getString("type", "string");
                        boolean isPrimaryKey = attr.getBoolean("primaryKey", false);
                        boolean isForeignKey = attr.getBoolean("foreignKey", false);
                        
                        String keyIndicator = "";
                        if (isPrimaryKey) keyIndicator = " PK";
                        else if (isForeignKey) keyIndicator = " FK";
                        
                        mermaid.append("        ")
                               .append(attrType).append(" ")
                               .append(attrName)
                               .append(keyIndicator)
                               .append("\n");
                    }
                }
                mermaid.append("    }\n");
            }
        }

        // Process relationships
        if (relationships != null) {
            for (Object relObj : relationships) {
                JsonObject relationship = (JsonObject) relObj;
                String fromEntity = relationship.getString("from");
                String toEntity = relationship.getString("to");
                String relationType = relationship.getString("type", "||--||"); // one-to-one default
                String label = relationship.getString("label", "");

                mermaid.append("    ")
                       .append(fromEntity)
                       .append(" ")
                       .append(relationType)
                       .append(" ")
                       .append(toEntity)
                       .append(" : ")
                       .append(label)
                       .append("\n");
            }
        }

        mermaid.append("```");
        
        logger.info(messageMarker, "Generated Mermaid ER diagram with {} entities and {} relationships", 
                   entities != null ? entities.size() : 0,
                   relationships != null ? relationships.size() : 0);
        
        return mermaid.toString();
    }

    private boolean isRequestValid(Message<JsonObject> message, Structured messageMarker) {
        if (message.body() == null) {
            logger.warn(messageMarker, "Body should be a valid JsonObject");
            message.fail(400, "Body should be a valid JsonObject");
            return false;
        }

        JsonObject body = message.body();
        if (body.isEmpty()) {
            logger.warn(messageMarker, "Request body cannot be empty");
            message.fail(400, "Request body cannot be empty");
            return false;
        }

        JsonArray entities = body.getJsonArray("entities");
        if (entities == null || entities.isEmpty()) {
            logger.warn(messageMarker, "Missing or empty 'entities' array in the request body");
            message.fail(400, "Missing or empty 'entities' array in the request body");
            return false;
        }

        return true;
    }
}